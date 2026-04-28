"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import health
from app.api.middleware.error_handler import ErrorHandlerMiddleware

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Simulated Trading Platform",
    description="A simulated trading platform for stocks and crypto with real market data",
    version="0.1.0",
    debug=settings.debug,
)

# Add middleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup handler."""
    logger.info(
        "Application startup",
        env=settings.app_env,
        debug=settings.debug,
        log_level=settings.log_level,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown handler."""
    logger.info("Application shutdown")
