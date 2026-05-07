"""Trading execution service for buy and sell orders."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Account, CryptoHolding, StockHolding, Transaction
from app.schemas.trading import BuyQuote, SellQuote

logger = get_logger(__name__)


class TradingExecutionService:
    """Service for executing buy and sell trades."""

    async def execute_buy(
        self,
        account_id: str,
        quote: BuyQuote,
        db_session: AsyncSession,
    ) -> Transaction:
        """Execute a buy order.

        Args:
            account_id: The account ID.
            quote: The buy quote to execute.
            db_session: The database session.

        Returns:
            The created Transaction record.

        Raises:
            ValueError: If the account has insufficient cash.
        """
        logger.info(
            "Executing buy",
            account_id=account_id,
            symbol=quote.symbol,
            quantity=str(quote.quantity),
            total_usd_value=str(quote.total_usd_value),
        )

        # Fetch account
        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        total_cost = quote.total_usd_value + quote.estimated_fees
        if account.cash_balance < total_cost:
            raise ValueError(
                f"Insufficient cash: balance {account.cash_balance}, required {total_cost}"
            )

        # Deduct cash
        account.cash_balance -= total_cost

        # Update or create holding
        if quote.asset_type == "stock":
            holding_result = await db_session.execute(
                select(StockHolding).where(
                    StockHolding.account_id == account_id,
                    StockHolding.symbol == quote.symbol,
                    StockHolding.exchange == quote.exchange,
                )
            )
            holding = holding_result.scalar_one_or_none()

            if holding is None:
                holding = StockHolding(
                    account_id=account_id,
                    symbol=quote.symbol,
                    exchange=quote.exchange,
                    currency=quote.currency,
                    quantity=quote.quantity,
                    avg_cost_basis=quote.usd_price_per_unit,
                    total_invested=quote.total_usd_value,
                )
                db_session.add(holding)
            else:
                new_total_invested = holding.total_invested + quote.total_usd_value
                new_quantity = holding.quantity + quote.quantity
                holding.quantity = new_quantity
                holding.avg_cost_basis = new_total_invested / new_quantity
                holding.total_invested = new_total_invested
        elif quote.asset_type == "crypto":
            holding_result = await db_session.execute(
                select(CryptoHolding).where(
                    CryptoHolding.account_id == account_id,
                    CryptoHolding.symbol == quote.symbol,
                )
            )
            holding = holding_result.scalar_one_or_none()

            if holding is None:
                holding = CryptoHolding(
                    account_id=account_id,
                    symbol=quote.symbol,
                    quantity=quote.quantity,
                    avg_cost_basis=quote.usd_price_per_unit,
                    total_invested=quote.total_usd_value,
                )
                db_session.add(holding)
            else:
                new_total_invested = holding.total_invested + quote.total_usd_value
                new_quantity = holding.quantity + quote.quantity
                holding.quantity = new_quantity
                holding.avg_cost_basis = new_total_invested / new_quantity
                holding.total_invested = new_total_invested
        else:
            raise ValueError(f"Unsupported asset type: {quote.asset_type}")

        # Create transaction
        transaction = Transaction(
            account_id=account_id,
            type="buy",
            asset_type=quote.asset_type,
            symbol=quote.symbol,
            exchange=quote.exchange,
            quantity=quote.quantity,
            price_per_unit=quote.price_per_unit,
            currency=quote.currency,
            exchange_rate=quote.exchange_rate,
            usd_price_per_unit=quote.usd_price_per_unit,
            total_usd_value=quote.total_usd_value,
            fees=quote.estimated_fees,
            status="CONFIRMED",
        )
        db_session.add(transaction)
        await db_session.commit()
        await db_session.refresh(transaction)

        logger.info(
            "Buy executed",
            transaction_id=transaction.id,
            account_id=account_id,
            symbol=quote.symbol,
        )
        return transaction

    async def execute_sell(
        self,
        account_id: str,
        quote: SellQuote,
        db_session: AsyncSession,
    ) -> Transaction:
        """Execute a sell order.

        Args:
            account_id: The account ID.
            quote: The sell quote to execute.
            db_session: The database session.

        Returns:
            The created Transaction record.

        Raises:
            ValueError: If the account does not hold enough of the asset.
        """
        logger.info(
            "Executing sell",
            account_id=account_id,
            symbol=quote.symbol,
            quantity=str(quote.quantity),
            total_usd_value=str(quote.total_usd_value),
        )

        # Fetch account
        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        # Validate and reduce holding
        if quote.asset_type == "stock":
            holding_result = await db_session.execute(
                select(StockHolding).where(
                    StockHolding.account_id == account_id,
                    StockHolding.symbol == quote.symbol,
                    StockHolding.exchange == quote.exchange,
                )
            )
            holding = holding_result.scalar_one_or_none()
        elif quote.asset_type == "crypto":
            holding_result = await db_session.execute(
                select(CryptoHolding).where(
                    CryptoHolding.account_id == account_id,
                    CryptoHolding.symbol == quote.symbol,
                )
            )
            holding = holding_result.scalar_one_or_none()
        else:
            raise ValueError(f"Unsupported asset type: {quote.asset_type}")

        if holding is None or holding.quantity < quote.quantity:
            available = holding.quantity if holding else Decimal("0")
            raise ValueError(
                f"Insufficient {quote.asset_type} holdings: requested {quote.quantity}, available {available}"
            )

        # Proportional cost basis reduction
        if holding.quantity > Decimal("0"):
            reduction_ratio = quote.quantity / holding.quantity
            invested_reduction = holding.total_invested * reduction_ratio
            holding.total_invested -= invested_reduction
        else:
            holding.total_invested = Decimal("0")

        holding.quantity -= quote.quantity

        if holding.quantity == Decimal("0"):
            await db_session.delete(holding)
        else:
            # avg_cost_basis stays the same for average cost method on partial sell
            holding.avg_cost_basis = holding.total_invested / holding.quantity

        # Add cash
        net_proceeds = quote.total_usd_value - quote.estimated_fees
        account.cash_balance += net_proceeds

        # Create transaction
        transaction = Transaction(
            account_id=account_id,
            type="sell",
            asset_type=quote.asset_type,
            symbol=quote.symbol,
            exchange=quote.exchange,
            quantity=quote.quantity,
            price_per_unit=quote.price_per_unit,
            currency=quote.currency,
            exchange_rate=quote.exchange_rate,
            usd_price_per_unit=quote.usd_price_per_unit,
            total_usd_value=quote.total_usd_value,
            fees=quote.estimated_fees,
            status="CONFIRMED",
        )
        db_session.add(transaction)
        await db_session.commit()
        await db_session.refresh(transaction)

        logger.info(
            "Sell executed",
            transaction_id=transaction.id,
            account_id=account_id,
            symbol=quote.symbol,
        )
        return transaction
