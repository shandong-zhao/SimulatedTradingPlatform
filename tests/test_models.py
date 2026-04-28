"""Tests for database models."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Account, StockHolding, CryptoHolding, Transaction


@pytest.mark.asyncio
class TestAccount:
    """Test Account model."""

    async def test_create_account(self, db_session):
        """Test creating an account."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        result = await db_session.execute(select(Account).where(Account.id == account.id))
        stored = result.scalar_one()
        assert stored.cash_balance == Decimal("100000.00")


@pytest.mark.asyncio
class TestStockHolding:
    """Test StockHolding model."""

    async def test_create_stock_holding(self, db_session):
        """Test creating a stock holding."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        holding = StockHolding(
            account_id=account.id,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            quantity=Decimal("10.5"),
            avg_cost_basis=Decimal("150.00"),
            total_invested=Decimal("1575.00"),
        )
        db_session.add(holding)
        await db_session.commit()

        result = await db_session.execute(select(StockHolding).where(StockHolding.id == holding.id))
        stored = result.scalar_one()
        assert stored.symbol == "AAPL"
        assert stored.quantity == Decimal("10.5")


@pytest.mark.asyncio
class TestTransaction:
    """Test Transaction model."""

    async def test_create_transaction(self, db_session):
        """Test creating a transaction."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        transaction = Transaction(
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
        db_session.add(transaction)
        await db_session.commit()

        result = await db_session.execute(select(Transaction).where(Transaction.id == transaction.id))
        stored = result.scalar_one()
        assert stored.type == "buy"
        assert stored.total_usd_value == Decimal("1500.00")
