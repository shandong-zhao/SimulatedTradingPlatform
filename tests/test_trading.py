"""Tests for trading engine — quotes, execution, and API endpoints."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, CryptoHolding, StockHolding
from app.schemas.trading import BuyQuote, SellQuote
from app.services.trading.execution import TradingExecutionService
from app.services.trading.quote import QuoteService


class FakePriceResolver:
    """Fake price resolver for testing."""

    def __init__(self, price: Decimal) -> None:
        self._price = price

    async def get_price(self, symbol: str) -> Decimal:
        return self._price


class FakeExchangeService:
    """Fake exchange service for testing."""

    async def get_rate(self, from_currency: str, to_currency: str) -> Decimal:
        if from_currency == to_currency:
            return Decimal("1")
        return Decimal("0.92")


@pytest.mark.asyncio
class TestQuoteService:
    """Test QuoteService."""

    async def test_generate_buy_quote_usd(self):
        """Test buy quote generation in USD."""
        service = QuoteService()
        service._price_resolver = FakePriceResolver(Decimal("150.00"))
        service._exchange_service = FakeExchangeService()

        quote = await service.generate_buy_quote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            usd_amount=Decimal("1500.00"),
            asset_type="stock",
        )

        assert quote.symbol == "AAPL"
        assert quote.exchange == "NASDAQ"
        assert quote.currency == "USD"
        assert quote.asset_type == "stock"
        assert quote.usd_price_per_unit == Decimal("150.00")
        assert quote.price_per_unit == Decimal("150.00")
        assert quote.exchange_rate == Decimal("1")
        assert quote.quantity == Decimal("10")
        assert quote.total_usd_value == Decimal("1500.00")
        assert quote.estimated_fees == Decimal("0")
        assert quote.preview is True

    async def test_generate_buy_quote_non_usd(self):
        """Test buy quote generation with currency conversion."""
        service = QuoteService()
        service._price_resolver = FakePriceResolver(Decimal("150.00"))
        service._exchange_service = FakeExchangeService()

        quote = await service.generate_buy_quote(
            symbol="AAPL",
            exchange="LSE",
            currency="GBP",
            usd_amount=Decimal("1500.00"),
            asset_type="stock",
        )

        assert quote.currency == "GBP"
        assert quote.exchange_rate == Decimal("0.92")
        assert quote.price_per_unit == Decimal("138.00")  # 150 * 0.92
        assert quote.quantity == Decimal("10")

    async def test_generate_sell_quote_with_holding(self, db_session):
        """Test sell quote when holding exists."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            total_invested=Decimal("1400.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        service = QuoteService()
        service._price_resolver = FakePriceResolver(Decimal("150.00"))
        service._exchange_service = FakeExchangeService()

        quote = await service.generate_sell_quote(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("5"),
            asset_type="stock",
            db_session=db_session,
        )

        assert quote.symbol == "AAPL"
        assert quote.quantity == Decimal("5")
        assert quote.usd_price_per_unit == Decimal("150.00")
        assert quote.total_usd_value == Decimal("750.00")
        assert quote.holding_quantity == Decimal("10")
        assert quote.avg_cost_basis == Decimal("140.00")
        assert quote.unrealized_pnl == Decimal("50.00")  # (150 - 140) * 5

    async def test_generate_sell_quote_insufficient_holding(self, db_session):
        """Test sell quote raises error when holding is insufficient."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        service = QuoteService()
        service._price_resolver = FakePriceResolver(Decimal("150.00"))
        service._exchange_service = FakeExchangeService()

        with pytest.raises(ValueError, match="Insufficient"):
            await service.generate_sell_quote(
                account_id=account.id,
                symbol="AAPL",
                exchange="NASDAQ",
                currency="USD",
                quantity=Decimal("5"),
                asset_type="stock",
                db_session=db_session,
            )

    async def test_generate_sell_quote_crypto(self, db_session):
        """Test sell quote for crypto holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = CryptoHolding(
            account_id=account.id,
            symbol="BTC",
            quantity=Decimal("0.5"),
            avg_cost_basis=Decimal("40000.00"),
            total_invested=Decimal("20000.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        service = QuoteService()
        service._price_resolver = FakePriceResolver(Decimal("50000.00"))
        service._exchange_service = FakeExchangeService()

        quote = await service.generate_sell_quote(
            account_id=account.id,
            symbol="BTC",
            exchange="BINANCE",
            currency="USD",
            quantity=Decimal("0.1"),
            asset_type="crypto",
            db_session=db_session,
        )

        assert quote.asset_type == "crypto"
        assert quote.quantity == Decimal("0.1")
        assert quote.total_usd_value == Decimal("5000.00")
        assert quote.unrealized_pnl == Decimal("1000.00")  # (50000 - 40000) * 0.1


@pytest.mark.asyncio
class TestTradingExecutionService:
    """Test TradingExecutionService."""

    async def test_execute_buy_new_holding(self, db_session):
        """Test buying a new stock holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.execute_buy(account.id, quote, db_session)

        assert transaction.type == "buy"
        assert transaction.asset_type == "stock"
        assert transaction.symbol == "AAPL"
        assert transaction.quantity == Decimal("10")
        assert transaction.status == "CONFIRMED"

        # Verify cash deducted
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("98500.00")

        # Verify holding created
        result = await db_session.execute(
            select(StockHolding).where(StockHolding.account_id == account.id)
        )
        holding = result.scalar_one()
        assert holding.symbol == "AAPL"
        assert holding.quantity == Decimal("10")
        assert holding.avg_cost_basis == Decimal("150.00")
        assert holding.total_invested == Decimal("1500.00")

    async def test_execute_buy_existing_holding(self, db_session):
        """Test buying more of an existing stock holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            total_invested=Decimal("1400.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        await service.execute_buy(account.id, quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        updated_holding = result.scalar_one()
        assert updated_holding.quantity == Decimal("20")
        assert updated_holding.total_invested == Decimal("2900.00")
        assert updated_holding.avg_cost_basis == Decimal("145.00")  # 2900 / 20

    async def test_execute_buy_insufficient_cash(self, db_session):
        """Test buy raises error when cash is insufficient."""
        account = Account(cash_balance=Decimal("100.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        with pytest.raises(ValueError, match="Insufficient cash"):
            await service.execute_buy(account.id, quote, db_session)

    async def test_execute_sell_partial(self, db_session):
        """Test selling part of a holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            total_invested=Decimal("1400.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        quote = SellQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("4"),
            total_usd_value=Decimal("600.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            unrealized_pnl=Decimal("40.00"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.execute_sell(account.id, quote, db_session)

        assert transaction.type == "sell"
        assert transaction.quantity == Decimal("4")
        assert transaction.status == "CONFIRMED"

        # Verify cash added
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("100600.00")

        # Verify holding reduced proportionally
        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        updated_holding = result.scalar_one()
        assert updated_holding.quantity == Decimal("6")
        assert updated_holding.total_invested == Decimal("840.00")  # 1400 * 0.6
        assert updated_holding.avg_cost_basis == Decimal("140.00")  # 840 / 6

    async def test_execute_sell_full(self, db_session):
        """Test selling entire holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = CryptoHolding(
            account_id=account.id,
            symbol="BTC",
            quantity=Decimal("0.5"),
            avg_cost_basis=Decimal("40000.00"),
            total_invested=Decimal("20000.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        quote = SellQuote(
            symbol="BTC",
            exchange="BINANCE",
            currency="USD",
            asset_type="crypto",
            price_per_unit=Decimal("50000.00"),
            usd_price_per_unit=Decimal("50000.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("0.5"),
            total_usd_value=Decimal("25000.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("0.5"),
            avg_cost_basis=Decimal("40000.00"),
            unrealized_pnl=Decimal("5000.00"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.execute_sell(account.id, quote, db_session)

        assert transaction.type == "sell"

        # Verify holding deleted
        result = await db_session.execute(
            select(CryptoHolding).where(
                CryptoHolding.account_id == account.id,
                CryptoHolding.symbol == "BTC",
            )
        )
        assert result.scalar_one_or_none() is None

        # Verify cash added
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("125000.00")

    async def test_execute_sell_insufficient_holding(self, db_session):
        """Test sell raises error when holding is insufficient."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = SellQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("0"),
            avg_cost_basis=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        with pytest.raises(ValueError, match="Insufficient"):
            await service.execute_sell(account.id, quote, db_session)

    async def test_execute_buy_crypto_new(self, db_session):
        """Test buying a new crypto holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="BTC",
            exchange="BINANCE",
            currency="USD",
            asset_type="crypto",
            price_per_unit=Decimal("50000.00"),
            usd_price_per_unit=Decimal("50000.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("0.1"),
            total_usd_value=Decimal("5000.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.execute_buy(account.id, quote, db_session)

        assert transaction.asset_type == "crypto"

        result = await db_session.execute(
            select(CryptoHolding).where(CryptoHolding.account_id == account.id)
        )
        holding = result.scalar_one()
        assert holding.symbol == "BTC"
        assert holding.quantity == Decimal("0.1")
        assert holding.avg_cost_basis == Decimal("50000.00")


@pytest.mark.asyncio
class TestTradingTwoStepFlow:
    """Test two-step confirmation flow (pending → confirmed)."""

    async def test_create_pending_buy(self, db_session):
        """Test creating a pending buy transaction."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.create_pending_buy(account.id, quote, db_session)

        assert transaction.status == "PENDING"
        assert transaction.type == "buy"
        assert transaction.symbol == "AAPL"

        # Cash should NOT be deducted yet
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("100000.00")

        # Holding should NOT be created yet
        result = await db_session.execute(
            select(StockHolding).where(StockHolding.account_id == account.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_confirm_buy(self, db_session):
        """Test confirming a pending buy transaction."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        pending = await service.create_pending_buy(account.id, quote, db_session)
        assert pending.status == "PENDING"

        confirmed = await service.confirm_buy(pending.id, db_session)
        assert confirmed.status == "CONFIRMED"
        assert confirmed.id == pending.id

        # Cash deducted after confirm
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("98500.00")

        # Holding created after confirm
        result = await db_session.execute(
            select(StockHolding).where(StockHolding.account_id == account.id)
        )
        holding = result.scalar_one()
        assert holding.quantity == Decimal("10")
        assert holding.avg_cost_basis == Decimal("150.00")

    async def test_confirm_buy_not_found(self, db_session):
        """Test confirming a non-existent transaction raises error."""
        service = TradingExecutionService()
        with pytest.raises(ValueError, match="not found"):
            await service.confirm_buy("nonexistent-id", db_session)

    async def test_confirm_buy_not_pending(self, db_session):
        """Test confirming a non-pending transaction raises error."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        pending = await service.create_pending_buy(account.id, quote, db_session)
        pending.status = "CONFIRMED"
        await db_session.commit()

        with pytest.raises(ValueError, match="not pending"):
            await service.confirm_buy(pending.id, db_session)

    async def test_create_pending_sell(self, db_session):
        """Test creating a pending sell transaction."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            total_invested=Decimal("1400.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        quote = SellQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("5"),
            total_usd_value=Decimal("750.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            unrealized_pnl=Decimal("50.00"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.create_pending_sell(account.id, quote, db_session)

        assert transaction.status == "PENDING"
        assert transaction.type == "sell"

        # Holding should still be intact
        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        updated_holding = result.scalar_one()
        assert updated_holding.quantity == Decimal("10")

        # Cash should NOT be added yet
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("100000.00")

    async def test_confirm_sell(self, db_session):
        """Test confirming a pending sell transaction."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            total_invested=Decimal("1400.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        quote = SellQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("4"),
            total_usd_value=Decimal("600.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            unrealized_pnl=Decimal("40.00"),
            preview=False,
        )

        service = TradingExecutionService()
        pending = await service.create_pending_sell(account.id, quote, db_session)
        assert pending.status == "PENDING"

        confirmed = await service.confirm_sell(pending.id, db_session)
        assert confirmed.status == "CONFIRMED"

        # Cash added after confirm
        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("100600.00")

        # Holding reduced after confirm
        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        updated_holding = result.scalar_one()
        assert updated_holding.quantity == Decimal("6")

    async def test_confirm_sell_not_found(self, db_session):
        """Test confirming a non-existent sell transaction raises error."""
        service = TradingExecutionService()
        with pytest.raises(ValueError, match="not found"):
            await service.confirm_sell("nonexistent-id", db_session)

    async def test_confirm_wrong_type(self, db_session):
        """Test confirming a buy transaction with confirm_sell raises error."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        pending = await service.create_pending_buy(account.id, quote, db_session)

        with pytest.raises(ValueError, match="not a sell"):
            await service.confirm_sell(pending.id, db_session)

    async def test_execute_buy_uses_two_step(self, db_session):
        """Test execute_buy delegates to two-step flow."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.execute_buy(account.id, quote, db_session)
        assert transaction.status == "CONFIRMED"

        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("98500.00")

    async def test_execute_sell_uses_two_step(self, db_session):
        """Test execute_sell delegates to two-step flow."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = CryptoHolding(
            account_id=account.id,
            symbol="BTC",
            quantity=Decimal("0.5"),
            avg_cost_basis=Decimal("40000.00"),
            total_invested=Decimal("20000.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        quote = SellQuote(
            symbol="BTC",
            exchange="BINANCE",
            currency="USD",
            asset_type="crypto",
            price_per_unit=Decimal("50000.00"),
            usd_price_per_unit=Decimal("50000.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("0.5"),
            total_usd_value=Decimal("25000.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("0.5"),
            avg_cost_basis=Decimal("40000.00"),
            unrealized_pnl=Decimal("5000.00"),
            preview=False,
        )

        service = TradingExecutionService()
        transaction = await service.execute_sell(account.id, quote, db_session)
        assert transaction.status == "CONFIRMED"

        result = await db_session.execute(
            select(CryptoHolding).where(
                CryptoHolding.account_id == account.id,
                CryptoHolding.symbol == "BTC",
            )
        )
        assert result.scalar_one_or_none() is None

        result = await db_session.execute(select(Account).where(Account.id == account.id))
        updated_account = result.scalar_one()
        assert updated_account.cash_balance == Decimal("125000.00")
