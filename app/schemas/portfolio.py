"""Portfolio schemas for request/response models."""

from decimal import Decimal

from pydantic import BaseModel, Field


class StockHoldingDetail(BaseModel):
    """Detailed stock holding with live price and returns."""

    symbol: str = Field(..., description="The asset symbol")
    exchange: str = Field(..., description="The exchange code")
    currency: str = Field(..., description="The currency code")
    quantity: Decimal = Field(..., description="Current quantity held")
    avg_cost_basis: Decimal = Field(..., description="Average cost basis in USD")
    total_invested: Decimal = Field(..., description="Total USD invested in this holding")
    current_price: Decimal = Field(..., description="Current market price in USD")
    current_value: Decimal = Field(..., description="Current USD value of holding")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss in USD")
    return_pct: Decimal = Field(..., description="Percentage return")


class CryptoHoldingDetail(BaseModel):
    """Detailed crypto holding with live price and returns."""

    symbol: str = Field(..., description="The asset symbol")
    quantity: Decimal = Field(..., description="Current quantity held")
    avg_cost_basis: Decimal = Field(..., description="Average cost basis in USD")
    total_invested: Decimal = Field(..., description="Total USD invested in this holding")
    current_price: Decimal = Field(..., description="Current market price in USD")
    current_value: Decimal = Field(..., description="Current USD value of holding")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss in USD")
    return_pct: Decimal = Field(..., description="Percentage return")


class PortfolioSummary(BaseModel):
    """Full portfolio summary for an account."""

    account_id: str = Field(..., description="The account ID")
    cash_balance: Decimal = Field(..., description="Available cash balance in USD")
    stock_holdings: list[StockHoldingDetail] = Field(
        default_factory=list, description="List of stock holdings"
    )
    crypto_holdings: list[CryptoHoldingDetail] = Field(
        default_factory=list, description="List of crypto holdings"
    )
    total_stock_value: Decimal = Field(..., description="Total USD value of stock holdings")
    total_crypto_value: Decimal = Field(..., description="Total USD value of crypto holdings")
    total_holdings_value: Decimal = Field(..., description="Total USD value of all holdings")
    total_value: Decimal = Field(..., description="Total portfolio value (cash + holdings)")
    total_invested: Decimal = Field(..., description="Total USD invested across all holdings")
    total_unrealized_pnl: Decimal = Field(..., description="Total unrealized PnL")
    total_return_pct: Decimal = Field(..., description="Total percentage return")


class HoldingsResponse(BaseModel):
    """Response model for holdings endpoint."""

    stock_holdings: list[StockHoldingDetail] = Field(default_factory=list)
    crypto_holdings: list[CryptoHoldingDetail] = Field(default_factory=list)


class TransactionHistoryItem(BaseModel):
    """Individual transaction record in history."""

    id: str = Field(..., description="Transaction ID")
    type: str = Field(..., description="Transaction type (buy/sell)")
    asset_type: str = Field(..., description="Asset type (stock/crypto)")
    symbol: str = Field(..., description="Asset symbol")
    exchange: str | None = Field(None, description="Exchange code")
    quantity: Decimal = Field(..., description="Quantity traded")
    price_per_unit: Decimal = Field(..., description="Price per unit in original currency")
    currency: str = Field(..., description="Currency code")
    exchange_rate: Decimal = Field(..., description="Exchange rate used")
    usd_price_per_unit: Decimal = Field(..., description="Price per unit in USD")
    total_usd_value: Decimal = Field(..., description="Total value in USD")
    fees: Decimal = Field(..., description="Fees charged")
    status: str = Field(..., description="Transaction status")
    timestamp: str | None = Field(None, description="Transaction timestamp")


class TransactionHistoryResponse(BaseModel):
    """Response model for transaction history."""

    transactions: list[TransactionHistoryItem] = Field(default_factory=list)
    total: int = Field(..., description="Total number of transactions")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")
