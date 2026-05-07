"""Tests for trading engine — quotes, execution, and API endpoints."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models import Account, CryptoHolding, StockHolding, Transaction
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
