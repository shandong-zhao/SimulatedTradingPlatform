"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import health, market
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.db.database import engine
from app.db.base import Base
from app.db.seed import seed_initial_account
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal

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
app.include_router(market.router)


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup handler."""
    logger.info(
        "Application startup",
        env=settings.app_env,
        debug=settings.debug,
        log_level=settings.log_level,
    )

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    # Seed initial account
    async with AsyncSessionLocal() as session:
        await seed_initial_account(session)
    logger.info("Initial account seeded")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown handler."""
    logger.info("Application shutdown")
    await engine.dispose()
