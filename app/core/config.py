"""Core application configuration."""

from decimal import Decimal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite:///./trading.db"

    # Default Account
    default_cash_balance: Decimal = Decimal("100000.00")

    # Market Data
    market_data_cache_ttl: int = 300
    yfinance_enabled: bool = True
    coingecko_enabled: bool = True

    # API Keys
    coingecko_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
