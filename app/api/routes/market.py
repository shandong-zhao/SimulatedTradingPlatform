"""Market data API endpoints."""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.market_data.exchange import ExchangeRateService
from app.services.market_data.resolver import PriceResolver

logger = get_logger(__name__)
router = APIRouter(prefix="/api/market", tags=["market"])


class PriceResponse(BaseModel):
    """Response model for price lookups."""

    symbol: str = Field(..., description="The asset symbol")
    price: Decimal = Field(..., description="The current price in USD")
    currency: str = Field(default="USD", description="The price currency")


class RateResponse(BaseModel):
    """Response model for exchange rate lookups."""

    from_currency: str = Field(..., description="Source currency")
    to_currency: str = Field(..., description="Target currency")
    rate: Decimal = Field(..., description="The exchange rate")


@router.get(
    "/price/{symbol}",
    response_model=PriceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current asset price",
    response_description="Returns the current price for the given symbol",
)
async def get_price(symbol: str) -> dict[str, Any]:
    """Get the current price for a stock or cryptocurrency symbol.

    Args:
        symbol: The asset symbol (e.g., "AAPL", "bitcoin")

    Returns:
        A dictionary with the symbol and current price.
    """
    logger.info("Price endpoint called", symbol=symbol)
    resolver = PriceResolver()

    try:
        price = await resolver.get_price(symbol)
    except Exception as exc:
        logger.error("Failed to get price", symbol=symbol, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to retrieve price for {symbol}: {str(exc)}",
        ) from exc

    return {
        "symbol": symbol.upper(),
        "price": price,
        "currency": "USD",
    }


@router.get(
    "/rates/{from_currency}/{to_currency}",
    response_model=RateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get exchange rate",
    response_description="Returns the exchange rate between two currencies",
)
async def get_rate(from_currency: str, to_currency: str) -> dict[str, Any]:
    """Get the exchange rate between two currencies.

    Args:
        from_currency: The source currency code (e.g., "EUR")
        to_currency: The target currency code (e.g., "USD")

    Returns:
        A dictionary with the exchange rate.
    """
    logger.info(
        "Rate endpoint called",
        from_currency=from_currency,
        to_currency=to_currency,
    )
    service = ExchangeRateService()

    try:
        rate = await service.get_rate(from_currency, to_currency)
    except Exception as exc:
        logger.error(
            "Failed to get exchange rate",
            from_currency=from_currency,
            to_currency=to_currency,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to retrieve exchange rate: {str(exc)}",
        ) from exc

    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "rate": rate,
    }
