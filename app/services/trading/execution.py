"""Trading execution service for buy and sell orders with two-step confirmation."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Account, CryptoHolding, StockHolding, Transaction
from app.schemas.trading import BuyQuote, SellQuote

logger = get_logger(__name__)


class TradingExecutionService:
    """Service for executing buy and sell trades with two-step confirmation."""

    # ------------------------------------------------------------------
    # Two-step flow: create pending → confirm
    # ------------------------------------------------------------------

    async def create_pending_buy(
        self,
        account_id: str,
        quote: BuyQuote,
        db_session: AsyncSession,
    ) -> Transaction:
        """Create a PENDING buy transaction (preview).

        Validates that the account has sufficient cash but does NOT deduct it yet.

        Args:
            account_id: The account ID.
            quote: The buy quote to preview.
            db_session: The database session.

        Returns:
            The created PENDING Transaction record.

        Raises:
            ValueError: If the account has insufficient cash or is not found.
        """
        logger.info(
            "Creating pending buy",
            account_id=account_id,
            symbol=quote.symbol,
            quantity=str(quote.quantity),
            total_usd_value=str(quote.total_usd_value),
        )

        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        total_cost = quote.total_usd_value + quote.estimated_fees
        if account.cash_balance < total_cost:
            raise ValueError(
                f"Insufficient cash: balance {account.cash_balance}, required {total_cost}"
            )

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
            status="PENDING",
        )
        db_session.add(transaction)
        await db_session.commit()
        await db_session.refresh(transaction)

        logger.info(
            "Pending buy created",
            transaction_id=transaction.id,
            account_id=account_id,
            symbol=quote.symbol,
        )
        return transaction

    async def confirm_buy(
        self,
        transaction_id: str,
        db_session: AsyncSession,
    ) -> Transaction:
        """Confirm a PENDING buy transaction and execute it.

        Args:
            transaction_id: The pending transaction ID.
            db_session: The database session.

        Returns:
            The confirmed Transaction record.

        Raises:
            ValueError: If the transaction is not found or not in PENDING status.
        """
        logger.info("Confirming buy", transaction_id=transaction_id)

        result = await db_session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            raise ValueError(f"Transaction {transaction_id} not found")
        if transaction.status != "PENDING":
            raise ValueError(f"Transaction {transaction_id} is not pending (status={transaction.status})")
        if transaction.type != "buy":
            raise ValueError(f"Transaction {transaction_id} is not a buy order")

        account_id = transaction.account_id
        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        total_cost = transaction.total_usd_value + transaction.fees
        if account.cash_balance < total_cost:
            raise ValueError(
                f"Insufficient cash: balance {account.cash_balance}, required {total_cost}"
            )

        # Deduct cash
        account.cash_balance -= total_cost

        # Update or create holding
        if transaction.asset_type == "stock":
            holding_result = await db_session.execute(
                select(StockHolding).where(
                    StockHolding.account_id == account_id,
                    StockHolding.symbol == transaction.symbol,
                    StockHolding.exchange == transaction.exchange,
                )
            )
            holding = holding_result.scalar_one_or_none()

            if holding is None:
                holding = StockHolding(
                    account_id=account_id,
                    symbol=transaction.symbol,
                    exchange=transaction.exchange,
                    currency=transaction.currency,
                    quantity=transaction.quantity,
                    avg_cost_basis=transaction.usd_price_per_unit,
                    total_invested=transaction.total_usd_value,
                )
                db_session.add(holding)
            else:
                new_total_invested = holding.total_invested + transaction.total_usd_value
                new_quantity = holding.quantity + transaction.quantity
                holding.quantity = new_quantity
                holding.avg_cost_basis = new_total_invested / new_quantity
                holding.total_invested = new_total_invested
        elif transaction.asset_type == "crypto":
            holding_result = await db_session.execute(
                select(CryptoHolding).where(
                    CryptoHolding.account_id == account_id,
                    CryptoHolding.symbol == transaction.symbol,
                )
            )
            holding = holding_result.scalar_one_or_none()

            if holding is None:
                holding = CryptoHolding(
                    account_id=account_id,
                    symbol=transaction.symbol,
                    quantity=transaction.quantity,
                    avg_cost_basis=transaction.usd_price_per_unit,
                    total_invested=transaction.total_usd_value,
                )
                db_session.add(holding)
            else:
                new_total_invested = holding.total_invested + transaction.total_usd_value
                new_quantity = holding.quantity + transaction.quantity
                holding.quantity = new_quantity
                holding.avg_cost_basis = new_total_invested / new_quantity
                holding.total_invested = new_total_invested
        else:
            raise ValueError(f"Unsupported asset type: {transaction.asset_type}")

        # Mark confirmed
        transaction.status = "CONFIRMED"
        await db_session.commit()
        await db_session.refresh(transaction)

        logger.info(
            "Buy confirmed",
            transaction_id=transaction.id,
            account_id=account_id,
            symbol=transaction.symbol,
        )
        return transaction

    async def create_pending_sell(
        self,
        account_id: str,
        quote: SellQuote,
        db_session: AsyncSession,
    ) -> Transaction:
        """Create a PENDING sell transaction (preview).

        Validates that the account holds enough of the asset but does NOT execute.

        Args:
            account_id: The account ID.
            quote: The sell quote to preview.
            db_session: The database session.

        Returns:
            The created PENDING Transaction record.

        Raises:
            ValueError: If the account does not hold enough of the asset.
        """
        logger.info(
            "Creating pending sell",
            account_id=account_id,
            symbol=quote.symbol,
            quantity=str(quote.quantity),
            total_usd_value=str(quote.total_usd_value),
        )

        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        # Validate holding
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
            status="PENDING",
        )
        db_session.add(transaction)
        await db_session.commit()
        await db_session.refresh(transaction)

        logger.info(
            "Pending sell created",
            transaction_id=transaction.id,
            account_id=account_id,
            symbol=quote.symbol,
        )
        return transaction

    async def confirm_sell(
        self,
        transaction_id: str,
        db_session: AsyncSession,
    ) -> Transaction:
        """Confirm a PENDING sell transaction and execute it.

        Args:
            transaction_id: The pending transaction ID.
            db_session: The database session.

        Returns:
            The confirmed Transaction record.

        Raises:
            ValueError: If the transaction is not found or not in PENDING status.
        """
        logger.info("Confirming sell", transaction_id=transaction_id)

        result = await db_session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            raise ValueError(f"Transaction {transaction_id} not found")
        if transaction.status != "PENDING":
            raise ValueError(f"Transaction {transaction_id} is not pending (status={transaction.status})")
        if transaction.type != "sell":
            raise ValueError(f"Transaction {transaction_id} is not a sell order")

        account_id = transaction.account_id
        result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        # Reduce holding
        if transaction.asset_type == "stock":
            holding_result = await db_session.execute(
                select(StockHolding).where(
                    StockHolding.account_id == account_id,
                    StockHolding.symbol == transaction.symbol,
                    StockHolding.exchange == transaction.exchange,
                )
            )
            holding = holding_result.scalar_one_or_none()
        elif transaction.asset_type == "crypto":
            holding_result = await db_session.execute(
                select(CryptoHolding).where(
                    CryptoHolding.account_id == account_id,
                    CryptoHolding.symbol == transaction.symbol,
                )
            )
            holding = holding_result.scalar_one_or_none()
        else:
            raise ValueError(f"Unsupported asset type: {transaction.asset_type}")

        if holding is None or holding.quantity < transaction.quantity:
            available = holding.quantity if holding else Decimal("0")
            raise ValueError(
                f"Insufficient {transaction.asset_type} holdings: requested {transaction.quantity}, available {available}"
            )

        # Proportional cost basis reduction
        if holding.quantity > Decimal("0"):
            reduction_ratio = transaction.quantity / holding.quantity
            invested_reduction = holding.total_invested * reduction_ratio
            holding.total_invested -= invested_reduction
        else:
            holding.total_invested = Decimal("0")

        holding.quantity -= transaction.quantity

        if holding.quantity == Decimal("0"):
            await db_session.delete(holding)
        else:
            holding.avg_cost_basis = holding.total_invested / holding.quantity

        # Add cash
        net_proceeds = transaction.total_usd_value - transaction.fees
        account.cash_balance += net_proceeds

        # Mark confirmed
        transaction.status = "CONFIRMED"
        await db_session.commit()
        await db_session.refresh(transaction)

        logger.info(
            "Sell confirmed",
            transaction_id=transaction.id,
            account_id=account_id,
            symbol=transaction.symbol,
        )
        return transaction

    # ------------------------------------------------------------------
    # Direct execution (backward compatibility / internal use)
    # ------------------------------------------------------------------

    async def execute_buy(
        self,
        account_id: str,
        quote: BuyQuote,
        db_session: AsyncSession,
    ) -> Transaction:
        """Execute a buy order directly (skips pending state).

        Args:
            account_id: The account ID.
            quote: The buy quote to execute.
            db_session: The database session.

        Returns:
            The created Transaction record with CONFIRMED status.
        """
        transaction = await self.create_pending_buy(account_id, quote, db_session)
        return await self.confirm_buy(transaction.id, db_session)

    async def execute_sell(
        self,
        account_id: str,
        quote: SellQuote,
        db_session: AsyncSession,
    ) -> Transaction:
        """Execute a sell order directly (skips pending state).

        Args:
            account_id: The account ID.
            quote: The sell quote to execute.
            db_session: The database session.

        Returns:
            The created Transaction record with CONFIRMED status.
        """
        transaction = await self.create_pending_sell(account_id, quote, db_session)
        return await self.confirm_sell(transaction.id, db_session)
