"""Database seed utility for initial data."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Account

logger = get_logger(__name__)


async def seed_initial_account(session: AsyncSession) -> Account:
    """Create initial account with default cash balance if none exists."""
    result = await session.execute(select(Account).limit(1))
    existing_account = result.scalar_one_or_none()

    if existing_account is not None:
        logger.info("Initial account already exists", account_id=existing_account.id)
        return existing_account

    account = Account(
        cash_balance=Decimal(str(settings.default_cash_balance)),
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)

    logger.info(
        "Created initial account",
        account_id=account.id,
        cash_balance=str(account.cash_balance),
    )

    return account
