"""Database models for the simulated trading platform."""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.sqlite import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Account(Base):
    """Trading account model."""

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    cash_balance: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=4), default=Decimal("0")
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    stock_holdings: Mapped[list["StockHolding"]] = relationship(
        "StockHolding", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )
    crypto_holdings: Mapped[list["CryptoHolding"]] = relationship(
        "CryptoHolding", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )


class StockHolding(Base):
    """Stock holding model."""

    __tablename__ = "stock_holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(precision=19, scale=8), default=Decimal("0"))
    avg_cost_basis: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=4), default=Decimal("0")
    )
    total_invested: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=4), default=Decimal("0")
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship("Account", back_populates="stock_holdings")


class CryptoHolding(Base):
    """Crypto holding model."""

    __tablename__ = "crypto_holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(precision=19, scale=8), default=Decimal("0"))
    avg_cost_basis: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=4), default=Decimal("0")
    )
    total_invested: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=4), default=Decimal("0")
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship("Account", back_populates="crypto_holdings")


class Transaction(Base):
    """Transaction model for trades."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" or "sell"
    asset_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "stock" or "crypto"
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(precision=19, scale=8), nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(DECIMAL(precision=19, scale=4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=8), default=Decimal("1")
    )
    usd_price_per_unit: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=19, scale=4), nullable=False
    )
    total_usd_value: Mapped[Decimal] = mapped_column(DECIMAL(precision=19, scale=4), nullable=False)
    fees: Mapped[Decimal] = mapped_column(DECIMAL(precision=19, scale=4), default=Decimal("0"))
    timestamp: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )  # PENDING, CONFIRMED, CANCELLED

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")
