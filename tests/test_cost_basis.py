"""Edge case tests for cost basis calculations."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, CryptoHolding, StockHolding
from app.services.trading.execution import TradingExecutionService
from app.services.trading.quote import BuyQuote, SellQuote


@pytest.mark.asyncio
class TestCostBasisEdgeCases:
    """Test cost basis calculation edge cases."""

    async def test_buy_new_holding_sets_cost_basis(self, db_session):
        """First buy sets avg_cost_basis to buy price."""
        account = Account(cash_balance=Decimal("100000"))
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
        tx = await service.execute_buy(account.id, quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        holding = result.scalar_one()

        assert holding.avg_cost_basis == Decimal("150.00")
        assert holding.total_invested == Decimal("1500.00")
        assert tx.status == "CONFIRMED"

    async def test_second_buy_updates_cost_basis(self, db_session):
        """Second buy updates avg_cost_basis using weighted average."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        service = TradingExecutionService()

        # First buy: 10 shares @ $100
        quote1 = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("100.00"),
            usd_price_per_unit=Decimal("100.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1000.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )
        await service.execute_buy(account.id, quote1, db_session)

        # Second buy: 5 shares @ $150
        quote2 = BuyQuote(
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
            preview=False,
        )
        await service.execute_buy(account.id, quote2, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        holding = result.scalar_one()

        # Weighted average: (10*100 + 5*150) / 15 = 116.6667 (rounded to 4 decimal places)
        assert holding.quantity == Decimal("15")
        assert holding.avg_cost_basis == Decimal("116.6667")
        assert holding.total_invested == Decimal("1750.00")

    async def test_partial_sell_preserves_cost_basis(self, db_session):
        """Partial sell does not change avg_cost_basis."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        service = TradingExecutionService()

        # Buy 10 shares @ $100
        buy_quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("100.00"),
            usd_price_per_unit=Decimal("100.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1000.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )
        await service.execute_buy(account.id, buy_quote, db_session)

        # Sell 4 shares @ $150
        sell_quote = SellQuote(
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
            avg_cost_basis=Decimal("100.00"),
            unrealized_pnl=Decimal("200.00"),
            preview=False,
        )
        await service.execute_sell(account.id, sell_quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        holding = result.scalar_one()

        assert holding.quantity == Decimal("6")
        # Cost basis should remain the same after partial sell
        assert holding.avg_cost_basis == Decimal("100.00")
        # Total invested reduced proportionally
        assert holding.total_invested == Decimal("600.00")

    async def test_sell_entire_position_removes_holding(self, db_session):
        """Selling all shares removes the holding."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        service = TradingExecutionService()

        # Buy 5 shares @ $200
        buy_quote = BuyQuote(
            symbol="TSLA",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("200.00"),
            usd_price_per_unit=Decimal("200.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("5"),
            total_usd_value=Decimal("1000.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )
        await service.execute_buy(account.id, buy_quote, db_session)

        # Sell all 5 shares
        sell_quote = SellQuote(
            symbol="TSLA",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("250.00"),
            usd_price_per_unit=Decimal("250.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("5"),
            total_usd_value=Decimal("1250.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("5"),
            avg_cost_basis=Decimal("200.00"),
            unrealized_pnl=Decimal("250.00"),
            preview=False,
        )
        await service.execute_sell(account.id, sell_quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "TSLA",
            )
        )
        holding = result.scalar_one_or_none()

        assert holding is None

    async def test_fractional_quantity_cost_basis(self, db_session):
        """Cost basis works with fractional quantities."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        service = TradingExecutionService()

        # Buy 0.5 BTC @ $50000
        buy_quote = BuyQuote(
            symbol="BTC",
            exchange="COINBASE",
            currency="USD",
            asset_type="crypto",
            price_per_unit=Decimal("50000.00"),
            usd_price_per_unit=Decimal("50000.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("0.5"),
            total_usd_value=Decimal("25000.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )
        await service.execute_buy(account.id, buy_quote, db_session)

        result = await db_session.execute(
            select(CryptoHolding).where(
                CryptoHolding.account_id == account.id,
                CryptoHolding.symbol == "BTC",
            )
        )
        holding = result.scalar_one()

        assert holding.quantity == Decimal("0.5")
        assert holding.avg_cost_basis == Decimal("50000.00")
        assert holding.total_invested == Decimal("25000.00")

    async def test_fractional_sell_updates_correctly(self, db_session):
        """Selling fractional quantity updates holding correctly."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        service = TradingExecutionService()

        # Buy 2.5 ETH @ $2000
        buy_quote = BuyQuote(
            symbol="ETH",
            exchange="COINBASE",
            currency="USD",
            asset_type="crypto",
            price_per_unit=Decimal("2000.00"),
            usd_price_per_unit=Decimal("2000.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("2.5"),
            total_usd_value=Decimal("5000.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )
        await service.execute_buy(account.id, buy_quote, db_session)

        # Sell 1.25 ETH
        sell_quote = SellQuote(
            symbol="ETH",
            exchange="COINBASE",
            currency="USD",
            asset_type="crypto",
            price_per_unit=Decimal("2200.00"),
            usd_price_per_unit=Decimal("2200.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("1.25"),
            total_usd_value=Decimal("2750.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("2.5"),
            avg_cost_basis=Decimal("2000.00"),
            unrealized_pnl=Decimal("250.00"),
            preview=False,
        )
        await service.execute_sell(account.id, sell_quote, db_session)

        result = await db_session.execute(
            select(CryptoHolding).where(
                CryptoHolding.account_id == account.id,
                CryptoHolding.symbol == "ETH",
            )
        )
        holding = result.scalar_one()

        assert holding.quantity == Decimal("1.25")
        assert holding.avg_cost_basis == Decimal("2000.00")
        assert holding.total_invested == Decimal("2500.00")

    async def test_multiple_buys_different_prices(self, db_session):
        """Multiple buys at different prices compute correct weighted average."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        service = TradingExecutionService()

        prices_quantities = [
            (Decimal("100.00"), Decimal("10")),
            (Decimal("200.00"), Decimal("5")),
            (Decimal("150.00"), Decimal("10")),
        ]

        total_shares = Decimal("0")
        total_cost = Decimal("0")

        for price, qty in prices_quantities:
            total_shares += qty
            total_cost += price * qty

            quote = BuyQuote(
                symbol="AAPL",
                exchange="NASDAQ",
                currency="USD",
                asset_type="stock",
                price_per_unit=price,
                usd_price_per_unit=price,
                exchange_rate=Decimal("1"),
                quantity=qty,
                total_usd_value=price * qty,
                estimated_fees=Decimal("0"),
                preview=False,
            )
            await service.execute_buy(account.id, quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "AAPL",
            )
        )
        holding = result.scalar_one()

        expected_avg = total_cost / total_shares  # (1000 + 1000 + 1500) / 25 = 140
        assert holding.quantity == total_shares
        assert holding.avg_cost_basis == expected_avg
        assert holding.total_invested == total_cost

    async def test_zero_dollar_buy(self, db_session):
        """Buy with zero total value should still create holding with zero cost basis."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        quote = BuyQuote(
            symbol="FREESTOCK",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("0.00"),
            usd_price_per_unit=Decimal("0.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("100"),
            total_usd_value=Decimal("0.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        tx = await service.execute_buy(account.id, quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "FREESTOCK",
            )
        )
        holding = result.scalar_one()

        assert holding.quantity == Decimal("100")
        # Zero cost basis when price is zero
        assert holding.avg_cost_basis == Decimal("0")
        assert holding.total_invested == Decimal("0")
        assert tx.status == "CONFIRMED"

    async def test_currency_conversion_cost_basis(self, db_session):
        """Cost basis in USD when buying with foreign currency."""
        account = Account(cash_balance=Decimal("100000"))
        db_session.add(account)
        await db_session.commit()

        # Buy on LSE: 10 shares @ GBP 10, exchange rate 1.25
        quote = BuyQuote(
            symbol="BP",
            exchange="LSE",
            currency="GBP",
            asset_type="stock",
            price_per_unit=Decimal("10.00"),
            usd_price_per_unit=Decimal("12.50"),  # 10 * 1.25
            exchange_rate=Decimal("1.25"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("125.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        service = TradingExecutionService()
        tx = await service.execute_buy(account.id, quote, db_session)

        result = await db_session.execute(
            select(StockHolding).where(
                StockHolding.account_id == account.id,
                StockHolding.symbol == "BP",
            )
        )
        holding = result.scalar_one()

        # Cost basis should be in USD
        assert holding.avg_cost_basis == Decimal("12.50")
        assert holding.total_invested == Decimal("125.00")
        assert tx.status == "CONFIRMED"
