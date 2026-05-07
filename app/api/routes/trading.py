"""Trading API endpoints for buy, sell, and quote generation."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbDependency
from app.core.logging import get_logger
from app.schemas.trading import (
    BuyQuote,
    BuyRequest,
    QuoteRequest,
    SellQuote,
    SellRequest,
    TransactionPreview,
    TransactionResponse,
)
from app.services.trading.execution import TradingExecutionService
from app.services.trading.quote import QuoteService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.post(
    "/quote",
    response_model=TransactionPreview,
    status_code=status.HTTP_200_OK,
    summary="Generate a trading quote",
    response_description="Returns a buy or sell quote preview",
)
async def generate_quote(
    request: QuoteRequest,
    db: AsyncSession = DbDependency,
) -> dict[str, Any]:
    """Generate a buy or sell quote preview.

    Args:
        request: The quote request with action and asset details.
        db: Database session.

    Returns:
        A TransactionPreview with the quote details.
    """
    logger.info(
        "Quote requested",
        action=request.action,
        symbol=request.symbol,
        asset_type=request.asset_type,
    )

    quote_service = QuoteService()
    action = request.action.lower()

    try:
        if action == "buy":
            if request.usd_amount is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="usd_amount is required for buy quotes",
                )
            quote: BuyQuote | SellQuote = await quote_service.generate_buy_quote(
                symbol=request.symbol,
                exchange=request.exchange,
                currency=request.currency,
                usd_amount=request.usd_amount,
                asset_type=request.asset_type,
            )
            return {"action": "buy", "quote": quote}
        elif action == "sell":
            if request.quantity is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="quantity is required for sell quotes",
                )
            quote = await quote_service.generate_sell_quote(
                account_id=request.account_id,
                symbol=request.symbol,
                exchange=request.exchange,
                currency=request.currency,
                quantity=request.quantity,
                asset_type=request.asset_type,
                db_session=db,
            )
            return {"action": "sell", "quote": quote}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {request.action}. Use 'buy' or 'sell'.",
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Quote generation failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to generate quote: {str(exc)}",
        ) from exc


@router.post(
    "/buy",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a buy order",
    response_description="Returns the completed transaction",
)
async def execute_buy(
    request: BuyRequest,
    db: AsyncSession = DbDependency,
) -> dict[str, Any]:
    """Execute a buy order.

    Args:
        request: The buy request details.
        db: Database session.

    Returns:
        The completed TransactionResponse.
    """
    logger.info(
        "Buy order requested",
        account_id=request.account_id,
        symbol=request.symbol,
        usd_amount=str(request.usd_amount),
    )

    quote_service = QuoteService()
    execution_service = TradingExecutionService()

    try:
        quote = await quote_service.generate_buy_quote(
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency,
            usd_amount=request.usd_amount,
            asset_type=request.asset_type,
        )
        transaction = await execution_service.execute_buy(
            account_id=request.account_id,
            quote=quote,
            db_session=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Buy execution failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to execute buy: {str(exc)}",
        ) from exc

    return {
        "id": transaction.id,
        "account_id": transaction.account_id,
        "type": transaction.type,
        "asset_type": transaction.asset_type,
        "symbol": transaction.symbol,
        "exchange": transaction.exchange,
        "quantity": transaction.quantity,
        "price_per_unit": transaction.price_per_unit,
        "currency": transaction.currency,
        "exchange_rate": transaction.exchange_rate,
        "usd_price_per_unit": transaction.usd_price_per_unit,
        "total_usd_value": transaction.total_usd_value,
        "fees": transaction.fees,
        "status": transaction.status,
        "timestamp": transaction.timestamp.isoformat() if transaction.timestamp else None,
    }


@router.post(
    "/sell",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a sell order",
    response_description="Returns the completed transaction",
)
async def execute_sell(
    request: SellRequest,
    db: AsyncSession = DbDependency,
) -> dict[str, Any]:
    """Execute a sell order.

    Args:
        request: The sell request details.
        db: Database session.

    Returns:
        The completed TransactionResponse.
    """
    logger.info(
        "Sell order requested",
        account_id=request.account_id,
        symbol=request.symbol,
        quantity=str(request.quantity),
    )

    quote_service = QuoteService()
    execution_service = TradingExecutionService()

    try:
        quote = await quote_service.generate_sell_quote(
            account_id=request.account_id,
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency,
            quantity=request.quantity,
            asset_type=request.asset_type,
            db_session=db,
        )
        transaction = await execution_service.execute_sell(
            account_id=request.account_id,
            quote=quote,
            db_session=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Sell execution failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to execute sell: {str(exc)}",
        ) from exc

    return {
        "id": transaction.id,
        "account_id": transaction.account_id,
        "type": transaction.type,
        "asset_type": transaction.asset_type,
        "symbol": transaction.symbol,
        "exchange": transaction.exchange,
        "quantity": transaction.quantity,
        "price_per_unit": transaction.price_per_unit,
        "currency": transaction.currency,
        "exchange_rate": transaction.exchange_rate,
        "usd_price_per_unit": transaction.usd_price_per_unit,
        "total_usd_value": transaction.total_usd_value,
        "fees": transaction.fees,
        "status": transaction.status,
        "timestamp": transaction.timestamp.isoformat() if transaction.timestamp else None,
    }
