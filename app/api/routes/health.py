"""Health check endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    response_description="Returns service health status",
)
async def health_check() -> dict[str, Any]:
    """Check if the service is healthy."""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }
