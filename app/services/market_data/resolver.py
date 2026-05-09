"""Unified price resolver with caching and fallback support."""

from collections.abc import Callable
from decimal import Decimal
from functools import wraps

from cachetools import TTLCache
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.coingecko import CoinGeckoProvider
from app.services.market_data.yahoo import YahooFinanceProvider

logger = get_logger(__name__)

# In-memory cache with configurable TTL
_price_cache: TTLCache = TTLCache(maxsize=1000, ttl=settings.market_data_cache_ttl)

# Common crypto symbols to detect asset type
_CRYPTO_SYMBOLS: set[str] = {
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "solana",
    "sol",
    "cardano",
    "ada",
    "polkadot",
    "dot",
    "ripple",
    "xrp",
    "litecoin",
    "ltc",
    "chainlink",
    "link",
}


def _cache_key(provider_name: str, symbol: str) -> str:
    """Generate a cache key for a price lookup.

    Args:
        provider_name: The name of the provider.
        symbol: The asset symbol.

    Returns:
        A unique cache key string.
    """
    return f"{provider_name}:{symbol.upper()}"


def _with_cache(func: Callable) -> Callable:
    """Decorator to cache price lookups.

    Args:
        func: The async function to wrap.

    Returns:
        The wrapped function with caching.
    """

    @wraps(func)
    async def wrapper(self: "PriceResolver", symbol: str) -> Decimal:  # type: ignore[return]
        provider_name = self._get_primary_provider(symbol).__class__.__name__
        key = _cache_key(provider_name, symbol)

        if key in _price_cache:
            logger.debug("Cache hit", symbol=symbol, provider=provider_name)
            return Decimal(str(_price_cache[key]))

        price = await func(self, symbol)
        _price_cache[key] = str(price)
        return price

    return wrapper


class PriceResolver:
    """Unified price resolver that routes to the correct provider."""

    def __init__(self) -> None:
        """Initialize the price resolver with providers."""
        self._yahoo = YahooFinanceProvider()
        self._coingecko = CoinGeckoProvider()

    def _is_crypto(self, symbol: str) -> bool:
        """Determine if a symbol is a cryptocurrency.

        Args:
            symbol: The asset symbol.

        Returns:
            True if the symbol appears to be a cryptocurrency.
        """
        return symbol.lower() in _CRYPTO_SYMBOLS

    def _get_primary_provider(self, symbol: str) -> MarketDataProvider:
        """Get the primary provider for a symbol.

        Args:
            symbol: The asset symbol.

        Returns:
            The primary market data provider.
        """
        if self._is_crypto(symbol):
            return self._coingecko
        return self._yahoo

    async def _get_fallback_provider(self, symbol: str) -> MarketDataProvider | None:
        """Get the fallback provider for a symbol.

        Args:
            symbol: The asset symbol.

        Returns:
            The fallback market data provider, or None if no fallback.
        """
        if self._is_crypto(symbol):
            if await self._yahoo.is_available():
                return self._yahoo
            return None
        if await self._coingecko.is_available():
            return self._coingecko
        return None

    @_with_cache
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def get_price(self, symbol: str) -> Decimal:
        """Get the current price for a symbol, with caching and fallback.

        Args:
            symbol: The asset symbol (e.g., "AAPL", "bitcoin")

        Returns:
            The current price in USD.

        Raises:
            Exception: If no provider can retrieve the price.
        """
        primary = self._get_primary_provider(symbol)
        fallback = await self._get_fallback_provider(symbol)

        # Try primary provider
        try:
            if await primary.is_available():
                price = await primary.get_price(symbol)
                logger.info("Price resolved", symbol=symbol, provider=primary.__class__.__name__)
                return price
        except Exception as exc:
            logger.warning(
                "Primary provider failed",
                symbol=symbol,
                provider=primary.__class__.__name__,
                error=str(exc),
            )

        # Try fallback provider
        if fallback is not None:
            try:
                price = await fallback.get_price(symbol)
                logger.info(
                    "Price resolved from fallback",
                    symbol=symbol,
                    provider=fallback.__class__.__name__,
                )
                return price
            except Exception as exc:
                logger.warning(
                    "Fallback provider failed",
                    symbol=symbol,
                    provider=fallback.__class__.__name__,
                    error=str(exc),
                )

        raise Exception(f"Unable to retrieve price for {symbol} from any provider")

    def clear_cache(self) -> None:
        """Clear the price cache."""
        _price_cache.clear()
        logger.info("Price cache cleared")
