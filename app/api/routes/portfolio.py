"""Portfolio API endpoints for holdings, summary, and transaction history."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbDependency
from app.core.logging import get_logger
from app.schemas.portfolio import (
    HoldingsResponse,
    PortfolioSummary,
    TransactionHistoryResponse,
)
from app.services.portfolio.portfolio import PortfolioService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get(
    "",
    response_model=PortfolioSummary,
    status_code=status.HTTP_200_OK,
    summary="Get full portfolio summary",
    response_description="Returns portfolio with holdings, cash, and returns",
)
async def get_portfolio(
    account_id: str = Query(..., description="The account ID"),
    db: AsyncSession = DbDependency,
) -> dict[str, Any]:
    """Get the full portfolio summary for an account.

    Args:
        account_id: The account ID.
        db: Database session.

    Returns:
        PortfolioSummary with all holdings, cash, and return calculations.
    """
    logger.info("Portfolio requested", account_id=account_id)

    service = PortfolioService()
    try:
        summary = await service.get_portfolio(account_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Portfolio fetch failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to retrieve portfolio: {str(exc)}",
        ) from exc

    return summary.model_dump()


@router.get(
    "/holdings",
    response_model=HoldingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get holdings list",
    response_description="Returns stock and crypto holdings",
)
async def get_holdings(
    account_id: str = Query(..., description="The account ID"),
    db: AsyncSession = DbDependency,
) -> dict[str, Any]:
    """Get the holdings list for an account.

    Args:
        account_id: The account ID.
        db: Database session.

    Returns:
        HoldingsResponse with stock and crypto holdings.
    """
    logger.info("Holdings requested", account_id=account_id)

    service = PortfolioService()
    try:
        holdings = await service.get_holdings(account_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Holdings fetch failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to retrieve holdings: {str(exc)}",
        ) from exc

    return holdings


@router.get(
    "/transactions",
    response_model=TransactionHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transaction history",
    response_description="Returns paginated transaction history",
)
async def get_transactions(
    account_id: str = Query(..., description="The account ID"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Results to skip"),
    db: AsyncSession = DbDependency,
) -> dict[str, Any]:
    """Get paginated transaction history for an account.

    Args:
        account_id: The account ID.
        limit: Max number of transactions to return.
        offset: Number of transactions to skip.
        db: Database session.

    Returns:
        TransactionHistoryResponse with transactions and pagination info.
    """
    logger.info("Transactions requested", account_id=account_id, limit=limit, offset=offset)

    service = PortfolioService()
    try:
        transactions = await service.get_transaction_history(account_id, db, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Transaction history fetch failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to retrieve transactions: {str(exc)}",
        ) from exc

    return {
        "transactions": transactions,
        "total": len(transactions),
        "limit": limit,
        "offset": offset,
    }
