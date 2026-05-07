"""Tests for portfolio service — holdings, summary, and transaction history."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models import Account, CryptoHolding, StockHolding, Transaction
from app.services.portfolio.portfolio import PortfolioService


class FakePriceResolver:
    """Fake price resolver for testing."""

    def __init__(self, price: Decimal) -> None:
        self._price = price

    async def get_price(self, symbol: str) -> Decimal:
        return self._price


@pytest.mark.asyncio
class TestPortfolioService:
    """Test PortfolioService."""

    async def test_get_portfolio_empty(self, db_session):
        """Test portfolio summary for account with no holdings."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        service = PortfolioService()
        service._price_resolver = FakePriceResolver(Decimal("150.00"))

        portfolio = await service.get_portfolio(account.id, db_session)

        assert portfolio.account_id == account.id
        assert portfolio.cash_balance == Decimal("100000.00")
        assert portfolio.total_value == Decimal("100000.00")
        assert portfolio.total_stock_value == Decimal("0")
        assert portfolio.total_crypto_value == Decimal("0")
        assert portfolio.total_holdings_value == Decimal("0")
        assert portfolio.total_unrealized_pnl == Decimal("0")
        assert portfolio.total_return_pct == Decimal("0")
        assert portfolio.stock_holdings == []
        assert portfolio.crypto_holdings == []

    async def test_get_portfolio_with_stock(self, db_session):
        """Test portfolio with a single stock holding."""
        account = Account(cash_balance=Decimal("98500.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("150.00"),
            total_invested=Decimal("1500.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        service = PortfolioService()
        service._price_resolver = FakePriceResolver(Decimal("160.00"))

        portfolio = await service.get_portfolio(account.id, db_session)

        assert portfolio.cash_balance == Decimal("98500.00")
        assert portfolio.total_stock_value == Decimal("1600.00")  # 10 * 160
        assert portfolio.total_value == Decimal("100100.00")  # 98500 + 1600
        assert portfolio.total_invested == Decimal("1500.00")
        assert portfolio.total_unrealized_pnl == Decimal("100.00")  # 1600 - 1500
        assert portfolio.total_return_pct == Decimal("6.666666666666666666666666667")  # (100/1500)*100

        # Check individual holding detail
        assert len(portfolio.stock_holdings) == 1
        h = portfolio.stock_holdings[0]
        assert h.symbol == "AAPL"
        assert h.quantity == Decimal("10")
        assert h.avg_cost_basis == Decimal("150.00")
        assert h.current_price == Decimal("160.00")
        assert h.current_value == Decimal("1600.00")
        assert h.unrealized_pnl == Decimal("100.00")

    async def test_get_portfolio_with_crypto(self, db_session):
        """Test portfolio with a crypto holding."""
        account = Account(cash_balance=Decimal("95000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = CryptoHolding(
            account_id=account.id,
            symbol="BTC",
            quantity=Decimal("0.1"),
            avg_cost_basis=Decimal("40000.00"),
            total_invested=Decimal("4000.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        service = PortfolioService()
        service._price_resolver = FakePriceResolver(Decimal("50000.00"))

        portfolio = await service.get_portfolio(account.id, db_session)

        assert portfolio.total_crypto_value == Decimal("5000.00")  # 0.1 * 50000
        assert portfolio.total_value == Decimal("100000.00")  # 95000 + 5000
        assert portfolio.total_unrealized_pnl == Decimal("1000.00")  # 5000 - 4000

        assert len(portfolio.crypto_holdings) == 1
        h = portfolio.crypto_holdings[0]
        assert h.symbol == "BTC"
        assert h.quantity == Decimal("0.1")
        assert h.current_price == Decimal("50000.00")
        assert h.unrealized_pnl == Decimal("1000.00")

    async def test_get_portfolio_mixed(self, db_session):
        """Test portfolio with both stock and crypto holdings."""
        account = Account(cash_balance=Decimal("90000.00"))
        db_session.add(account)
        await db_session.commit()

        stock = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("150.00"),
            total_invested=Decimal("1500.00"),
        )
        crypto = CryptoHolding(
            account_id=account.id,
            symbol="BTC",
            quantity=Decimal("0.1"),
            avg_cost_basis=Decimal("40000.00"),
            total_invested=Decimal("4000.00"),
        )
        db_session.add(stock)
        db_session.add(crypto)
        await db_session.commit()

        service = PortfolioService()
        service._price_resolver = FakePriceResolver(Decimal("100.00"))

        portfolio = await service.get_portfolio(account.id, db_session)

        # Stock: 10 * 100 = 1000, invested 1500, pnl = -500
        # Crypto: 0.1 * 100 = 10, invested 4000, pnl = -3990
        assert portfolio.total_stock_value == Decimal("1000.00")
        assert portfolio.total_crypto_value == Decimal("10.00")
        assert portfolio.total_holdings_value == Decimal("1010.00")
        assert portfolio.total_value == Decimal("91010.00")
        assert portfolio.total_invested == Decimal("5500.00")
        assert portfolio.total_unrealized_pnl == Decimal("-4490.00")

    async def test_get_portfolio_account_not_found(self, db_session):
        """Test portfolio raises error for missing account."""
        service = PortfolioService()
        with pytest.raises(ValueError, match="Account .* not found"):
            await service.get_portfolio("nonexistent-id", db_session)

    async def test_get_holdings(self, db_session):
        """Test holdings list endpoint data."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        stock = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("150.00"),
            total_invested=Decimal("1500.00"),
        )
        db_session.add(stock)
        await db_session.commit()

        service = PortfolioService()
        service._price_resolver = FakePriceResolver(Decimal("160.00"))

        holdings = await service.get_holdings(account.id, db_session)

        assert len(holdings["stock_holdings"]) == 1
        assert len(holdings["crypto_holdings"]) == 0
        assert holdings["stock_holdings"][0].symbol == "AAPL"

    async def test_get_transaction_history(self, db_session):
        """Test transaction history retrieval."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        tx1 = Transaction(
            account_id=account.id,
            type="buy",
            asset_type="stock",
            symbol="AAPL",
            exchange="NASDAQ",
            quantity=Decimal("10"),
            price_per_unit=Decimal("150.00"),
            currency="USD",
            exchange_rate=Decimal("1"),
            usd_price_per_unit=Decimal("150.00"),
            total_usd_value=Decimal("1500.00"),
            fees=Decimal("0"),
            status="CONFIRMED",
        )
        tx2 = Transaction(
            account_id=account.id,
            type="sell",
            asset_type="stock",
            symbol="AAPL",
            exchange="NASDAQ",
            quantity=Decimal("5"),
            price_per_unit=Decimal("160.00"),
            currency="USD",
            exchange_rate=Decimal("1"),
            usd_price_per_unit=Decimal("160.00"),
            total_usd_value=Decimal("800.00"),
            fees=Decimal("0"),
            status="CONFIRMED",
        )
        db_session.add(tx1)
        db_session.add(tx2)
        await db_session.commit()

        service = PortfolioService()
        history = await service.get_transaction_history(account.id, db_session)

        assert len(history) == 2
        # Both have same timestamp from server_default; just verify both exist
        types = {h.type for h in history}
        assert types == {"buy", "sell"}

    async def test_get_transaction_history_pagination(self, db_session):
        """Test transaction history pagination."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        for i in range(5):
            tx = Transaction(
                account_id=account.id,
                type="buy",
                asset_type="stock",
                symbol="AAPL",
                exchange="NASDAQ",
                quantity=Decimal("1"),
                price_per_unit=Decimal("150.00"),
                currency="USD",
                exchange_rate=Decimal("1"),
                usd_price_per_unit=Decimal("150.00"),
                total_usd_value=Decimal("150.00"),
                fees=Decimal("0"),
                status="CONFIRMED",
            )
            db_session.add(tx)
        await db_session.commit()

        service = PortfolioService()
        history = await service.get_transaction_history(account.id, db_session, limit=2, offset=1)

        assert len(history) == 2

    async def test_get_transaction_history_account_not_found(self, db_session):
        """Test transaction history raises error for missing account."""
        service = PortfolioService()
        with pytest.raises(ValueError, match="Account .* not found"):
            await service.get_transaction_history("nonexistent-id", db_session)

    async def test_return_pct_zero_invested(self, db_session):
        """Test return percentage is 0 when nothing invested."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        # Create holding with 0 total_invested (edge case)
        stock = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10"),
            avg_cost_basis=Decimal("0"),
            total_invested=Decimal("0"),
        )
        db_session.add(stock)
        await db_session.commit()

        service = PortfolioService()
        service._price_resolver = FakePriceResolver(Decimal("150.00"))

        portfolio = await service.get_portfolio(account.id, db_session)

        assert portfolio.total_return_pct == Decimal("0")
        assert portfolio.stock_holdings[0].return_pct == Decimal("0")
