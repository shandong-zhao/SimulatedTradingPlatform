"""Pytest configuration and fixtures."""

import tempfile
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Account, StockHolding, CryptoHolding, Transaction


@pytest.fixture
async def db_engine():
    """Create a test database engine."""
    db_path = tempfile.mktemp(suffix=".db")
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    import os
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
async def db_session(db_engine):
    """Create a test database session."""
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
