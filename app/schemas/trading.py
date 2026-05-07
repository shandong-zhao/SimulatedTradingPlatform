"""Trading schemas for request/response models."""

from decimal import Decimal

from pydantic import BaseModel, Field


class BuyRequest(BaseModel):
    """Request model for a buy order."""

    account_id: str = Field(..., description="The account ID")
    symbol: str = Field(..., description="The asset symbol")
    exchange: str = Field(..., description="The exchange code")
    currency: str = Field(..., description="The currency code")
    usd_amount: Decimal = Field(..., description="The amount in USD to invest")
    asset_type: str = Field(..., description="The asset type (stock or crypto)")


class SellRequest(BaseModel):
    """Request model for a sell order."""

    account_id: str = Field(..., description="The account ID")
    symbol: str = Field(..., description="The asset symbol")
    exchange: str = Field(..., description="The exchange code")
    currency: str = Field(..., description="The currency code")
    quantity: Decimal = Field(..., description="The quantity to sell")
    asset_type: str = Field(..., description="The asset type (stock or crypto)")


class BuyQuote(BaseModel):
    """Quote response for a buy order preview."""

    symbol: str = Field(..., description="The asset symbol")
    exchange: str = Field(..., description="The exchange code")
    currency: str = Field(..., description="The currency code")
    asset_type: str = Field(..., description="The asset type (stock or crypto)")
    price_per_unit: Decimal = Field(..., description="Price per unit in original currency")
    usd_price_per_unit: Decimal = Field(..., description="Price per unit in USD")
    exchange_rate: Decimal = Field(..., description="USD to local currency exchange rate")
    quantity: Decimal = Field(..., description="The quantity that can be purchased")
    total_usd_value: Decimal = Field(..., description="Total value in USD")
    estimated_fees: Decimal = Field(default=Decimal("0"), description="Estimated fees")
    preview: bool = Field(default=True, description="Whether this is a preview")


class SellQuote(BaseModel):
    """Quote response for a sell order preview."""

    symbol: str = Field(..., description="The asset symbol")
    exchange: str = Field(..., description="The exchange code")
    currency: str = Field(..., description="The currency code")
    asset_type: str = Field(..., description="The asset type (stock or crypto)")
    price_per_unit: Decimal = Field(..., description="Price per unit in original currency")
    usd_price_per_unit: Decimal = Field(..., description="Price per unit in USD")
    exchange_rate: Decimal = Field(..., description="USD to local currency exchange rate")
    quantity: Decimal = Field(..., description="The quantity to sell")
    total_usd_value: Decimal = Field(..., description="Total value in USD")
    estimated_fees: Decimal = Field(default=Decimal("0"), description="Estimated fees")
    holding_quantity: Decimal = Field(..., description="Current holding quantity")
    avg_cost_basis: Decimal = Field(..., description="Average cost basis in USD")
    unrealized_pnl: Decimal = Field(..., description="Unrealized PnL in USD")
    preview: bool = Field(default=True, description="Whether this is a preview")


class TransactionPreview(BaseModel):
    """Preview response for a quote request."""

    action: str = Field(..., description="The action type (buy or sell)")
    quote: BuyQuote | SellQuote = Field(..., description="The quote details")


class TransactionResponse(BaseModel):
    """Response model for a completed transaction."""

    id: str = Field(..., description="The transaction ID")
    account_id: str = Field(..., description="The account ID")
    type: str = Field(..., description="The transaction type (buy or sell)")
    asset_type: str = Field(..., description="The asset type (stock or crypto)")
    symbol: str = Field(..., description="The asset symbol")
    exchange: str | None = Field(None, description="The exchange code")
    quantity: Decimal = Field(..., description="The quantity traded")
    price_per_unit: Decimal = Field(..., description="Price per unit in original currency")
    currency: str = Field(..., description="The currency code")
    exchange_rate: Decimal = Field(..., description="The exchange rate used")
    usd_price_per_unit: Decimal = Field(..., description="Price per unit in USD")
    total_usd_value: Decimal = Field(..., description="Total value in USD")
    fees: Decimal = Field(..., description="The fees charged")
    status: str = Field(..., description="The transaction status")
    timestamp: str | None = Field(None, description="The transaction timestamp")


class QuoteRequest(BaseModel):
    """Request model for generating a quote."""

    action: str = Field(..., description="The action type (buy or sell)")
    account_id: str = Field(..., description="The account ID")
    symbol: str = Field(..., description="The asset symbol")
    exchange: str = Field(..., description="The exchange code")
    currency: str = Field(..., description="The currency code")
    asset_type: str = Field(..., description="The asset type (stock or crypto)")
    usd_amount: Decimal | None = Field(None, description="The amount in USD to invest (for buy)")
    quantity: Decimal | None = Field(None, description="The quantity to sell (for sell)")
