"""Portfolio service for aggregating account data and calculating returns."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Account, Transaction
from app.schemas.portfolio import (
    CryptoHoldingDetail,
    PortfolioSummary,
    StockHoldingDetail,
    TransactionHistoryItem,
)
from app.services.market_data.resolver import PriceResolver

logger = get_logger(__name__)


class PortfolioService:
    """Service for portfolio aggregation and return calculations."""

    def __init__(self) -> None:
        """Initialize with price resolver."""
        self._price_resolver = PriceResolver()

    async def get_portfolio(
        self,
        account_id: str,
        db_session: AsyncSession,
    ) -> PortfolioSummary:
        """Get full portfolio summary for an account.

        Args:
            account_id: The account ID.
            db_session: The database session.

        Returns:
            PortfolioSummary with holdings, cash, totals, and returns.

        Raises:
            ValueError: If account not found.
        """
        logger.info("Fetching portfolio", account_id=account_id)

        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        cash = account.cash_balance
        stock_details = await self._get_stock_holdings(account, db_session)
        crypto_details = await self._get_crypto_holdings(account, db_session)

        total_stock_value = sum(h.current_value for h in stock_details)
        total_crypto_value = sum(h.current_value for h in crypto_details)
        total_holdings_value = total_stock_value + total_crypto_value
        total_value = cash + total_holdings_value

        total_invested = sum(h.total_invested for h in stock_details) + sum(
            h.total_invested for h in crypto_details
        )
        total_unrealized_pnl = sum(h.unrealized_pnl for h in stock_details) + sum(
            h.unrealized_pnl for h in crypto_details
        )

        total_return_pct = Decimal("0")
        if total_invested > Decimal("0"):
            total_return_pct = (total_unrealized_pnl / total_invested) * Decimal("100")

        return PortfolioSummary(
            account_id=account_id,
            cash_balance=cash,
            stock_holdings=stock_details,
            crypto_holdings=crypto_details,
            total_stock_value=total_stock_value,
            total_crypto_value=total_crypto_value,
            total_holdings_value=total_holdings_value,
            total_value=total_value,
            total_invested=total_invested,
            total_unrealized_pnl=total_unrealized_pnl,
            total_return_pct=total_return_pct,
        )

    async def _get_stock_holdings(
        self,
        account: Account,
        db_session: AsyncSession,
    ) -> list[StockHoldingDetail]:
        """Build stock holding details with live prices and returns."""
        details: list[StockHoldingDetail] = []
        for holding in account.stock_holdings:
            try:
                price = await self._price_resolver.get_price(holding.symbol)
            except Exception:
                price = Decimal("0")
            current_value = holding.quantity * price
            unrealized_pnl = current_value - holding.total_invested
            return_pct = Decimal("0")
            if holding.total_invested > Decimal("0"):
                return_pct = (unrealized_pnl / holding.total_invested) * Decimal("100")
            details.append(
                StockHoldingDetail(
                    symbol=holding.symbol,
                    exchange=holding.exchange,
                    currency=holding.currency,
                    quantity=holding.quantity,
                    avg_cost_basis=holding.avg_cost_basis,
                    total_invested=holding.total_invested,
                    current_price=price,
                    current_value=current_value,
                    unrealized_pnl=unrealized_pnl,
                    return_pct=return_pct,
                )
            )
        return details

    async def _get_crypto_holdings(
        self,
        account: Account,
        db_session: AsyncSession,
    ) -> list[CryptoHoldingDetail]:
        """Build crypto holding details with live prices and returns."""
        details: list[CryptoHoldingDetail] = []
        for holding in account.crypto_holdings:
            try:
                price = await self._price_resolver.get_price(holding.symbol)
            except Exception:
                price = Decimal("0")
            current_value = holding.quantity * price
            unrealized_pnl = current_value - holding.total_invested
            return_pct = Decimal("0")
            if holding.total_invested > Decimal("0"):
                return_pct = (unrealized_pnl / holding.total_invested) * Decimal("100")
            details.append(
                CryptoHoldingDetail(
                    symbol=holding.symbol,
                    quantity=holding.quantity,
                    avg_cost_basis=holding.avg_cost_basis,
                    total_invested=holding.total_invested,
                    current_price=price,
                    current_value=current_value,
                    unrealized_pnl=unrealized_pnl,
                    return_pct=return_pct,
                )
            )
        return details

    async def get_holdings(
        self,
        account_id: str,
        db_session: AsyncSession,
    ) -> dict[str, Any]:
        """Get holdings list for an account.

        Returns:
            Dict with stock_holdings and crypto_holdings lists.
        """
        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        stock_details = await self._get_stock_holdings(account, db_session)
        crypto_details = await self._get_crypto_holdings(account, db_session)
        return {
            "stock_holdings": stock_details,
            "crypto_holdings": crypto_details,
        }

    async def get_transaction_history(
        self,
        account_id: str,
        db_session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TransactionHistoryItem]:
        """Get paginated transaction history for an account.

        Args:
            account_id: The account ID.
            db_session: The database session.
            limit: Max number of transactions to return.
            offset: Number of transactions to skip.

        Returns:
            List of TransactionHistoryItem.

        Raises:
            ValueError: If account not found.
        """
        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        stmt = (
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        tx_result = await db_session.execute(stmt)
        transactions = tx_result.scalars().all()

        return [
            TransactionHistoryItem(
                id=tx.id,
                type=tx.type,
                asset_type=tx.asset_type,
                symbol=tx.symbol,
                exchange=tx.exchange,
                quantity=tx.quantity,
                price_per_unit=tx.price_per_unit,
                currency=tx.currency,
                exchange_rate=tx.exchange_rate,
                usd_price_per_unit=tx.usd_price_per_unit,
                total_usd_value=tx.total_usd_value,
                fees=tx.fees,
                status=tx.status,
                timestamp=tx.timestamp.isoformat() if tx.timestamp else None,
            )
            for tx in transactions
        ]
