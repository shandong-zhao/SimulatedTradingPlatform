"""Yahoo Finance market data provider for stock prices."""

import asyncio
from decimal import Decimal, InvalidOperation

import yfinance as yf

from app.core.config import settings
from app.core.logging import get_logger
from app.services.market_data.base import MarketDataProvider

logger = get_logger(__name__)


class YahooFinanceProvider(MarketDataProvider):
    """Yahoo Finance provider for stock prices."""

    def __init__(self) -> None:
        """Initialize the Yahoo Finance provider."""
        self._enabled = settings.yfinance_enabled

    async def is_available(self) -> bool:
        """Check if Yahoo Finance is enabled.

        Returns:
            True if enabled, False otherwise.
        """
        return self._enabled

    async def get_price(self, symbol: str) -> Decimal:
        """Get the current stock price from Yahoo Finance.

        Args:
            symbol: The stock symbol (e.g., "AAPL", "MSFT")

        Returns:
            The current price in USD.

        Raises:
            ValueError: If the price cannot be parsed.
            Exception: If the ticker data cannot be retrieved.
        """
        logger.debug("Fetching Yahoo Finance price", symbol=symbol)

        ticker = yf.Ticker(symbol)

        # yfinance is synchronous, run in thread pool
        info = await asyncio.to_thread(lambda: ticker.info)

        # Try common price fields
        price_keys = ["currentPrice", "regularMarketPrice", "previousClose", "navPrice"]
        raw_price = None
        for key in price_keys:
            raw_price = info.get(key)
            if raw_price is not None:
                break

        if raw_price is None:
            raise Exception(f"No price data found for {symbol} from Yahoo Finance")

        try:
            price = Decimal(str(raw_price))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid price value for {symbol}: {raw_price}") from exc

        logger.debug("Yahoo Finance price fetched", symbol=symbol, price=str(price))
        return price
