"""FastAPI dependency injection utilities."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session."""
    async for session in get_session():
        yield session


# Type alias for the dependency
DbDependency = Depends(get_db)
