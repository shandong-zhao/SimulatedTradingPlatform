"""API integration tests for trading endpoints."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models import Account, StockHolding
from app.schemas.trading import BuyQuote, SellQuote
from app.services.trading.execution import TradingExecutionService
from app.services.trading.quote import QuoteService


async def _mock_buy_quote(*args, **kwargs):
    return BuyQuote(
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


async def _mock_sell_quote(*args, **kwargs):
    return SellQuote(
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


@pytest.mark.asyncio
class TestBuyAPIEndpoints:
    """Integration tests for buy endpoints."""

    async def test_buy_preview_creates_pending(self, db_session):
        """POST /api/trading/buy creates a PENDING transaction."""
        account = Account(cash_balance=Decimal("100000.00"))
        db_session.add(account)
        await db_session.commit()

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        original = QuoteService.generate_buy_quote
        QuoteService.generate_buy_quote = _mock_buy_quote
        client = TestClient(app)

        try:
            response = client.post(
                "/api/trading/buy",
                json={
                    "account_id": account.id,
                    "symbol": "AAPL",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "usd_amount": "1500.00",
                    "asset_type": "stock",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "PENDING"
            assert data["type"] == "buy"
            assert data["symbol"] == "AAPL"
            assert "id" in data

            # Cash should not be deducted
            result = await db_session.execute(select(Account).where(Account.id == account.id))
            updated = result.scalar_one()
            assert updated.cash_balance == Decimal("100000.00")
        finally:
            QuoteService.generate_buy_quote = original
            app.dependency_overrides.pop(get_db, None)

    async def test_buy_confirm_executes_trade(self, db_session):
        """POST /api/trading/buy/confirm confirms a pending buy."""
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

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            response = client.post(
                "/api/trading/buy/confirm",
                json={"transaction_id": pending.id},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "CONFIRMED"
            assert data["id"] == pending.id
            assert data["type"] == "buy"
            assert data["quantity"] == "10.00000000"

            # Cash deducted
            result = await db_session.execute(select(Account).where(Account.id == account.id))
            updated = result.scalar_one()
            assert updated.cash_balance == Decimal("98500.00")
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_buy_confirm_not_found(self, db_session):
        """Confirming a non-existent transaction returns 400."""

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            response = client.post(
                "/api/trading/buy/confirm",
                json={"transaction_id": "nonexistent-id"},
            )
            assert response.status_code == 400
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
class TestSellAPIEndpoints:
    """Integration tests for sell endpoints."""

    async def test_sell_preview_creates_pending(self, db_session):
        """POST /api/trading/sell creates a PENDING transaction."""
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

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        original = QuoteService.generate_sell_quote
        QuoteService.generate_sell_quote = _mock_sell_quote
        client = TestClient(app)

        try:
            response = client.post(
                "/api/trading/sell",
                json={
                    "account_id": account.id,
                    "symbol": "AAPL",
                    "exchange": "NASDAQ",
                    "currency": "USD",
                    "quantity": "5",
                    "asset_type": "stock",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "PENDING"
            assert data["type"] == "sell"
            assert data["symbol"] == "AAPL"

            # Holding should still be intact
            result = await db_session.execute(
                select(StockHolding).where(
                    StockHolding.account_id == account.id,
                    StockHolding.symbol == "AAPL",
                )
            )
            updated = result.scalar_one()
            assert updated.quantity == Decimal("10")
        finally:
            QuoteService.generate_sell_quote = original
            app.dependency_overrides.pop(get_db, None)

    async def test_sell_confirm_executes_trade(self, db_session):
        """POST /api/trading/sell/confirm confirms a pending sell."""
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

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            response = client.post(
                "/api/trading/sell/confirm",
                json={"transaction_id": pending.id},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "CONFIRMED"
            assert data["id"] == pending.id
            assert data["type"] == "sell"
            assert data["quantity"] == "4.00000000"

            # Cash added
            result = await db_session.execute(select(Account).where(Account.id == account.id))
            updated = result.scalar_one()
            assert updated.cash_balance == Decimal("100600.00")
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_sell_confirm_not_found(self, db_session):
        """Confirming a non-existent sell returns 400."""

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            response = client.post(
                "/api/trading/sell/confirm",
                json={"transaction_id": "nonexistent-id"},
            )
            assert response.status_code == 400
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_db, None)
