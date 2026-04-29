"""CoinGecko market data provider for cryptocurrency prices."""

import asyncio
from decimal import Decimal, InvalidOperation

from pycoingecko import CoinGeckoAPI

from app.core.config import settings
from app.core.logging import get_logger
from app.services.market_data.base import MarketDataProvider

logger = get_logger(__name__)

# Mapping of common symbols to CoinGecko IDs
SYMBOL_TO_ID: dict[str, str] = {
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "solana": "solana",
    "sol": "solana",
    "cardano": "cardano",
    "ada": "cardano",
    "polkadot": "polkadot",
    "dot": "polkadot",
    "ripple": "ripple",
    "xrp": "ripple",
    "litecoin": "litecoin",
    "ltc": "litecoin",
    "chainlink": "chainlink",
    "link": "chainlink",
}


class CoinGeckoProvider(MarketDataProvider):
    """CoinGecko provider for cryptocurrency prices."""

    def __init__(self) -> None:
        """Initialize the CoinGecko provider."""
        self._enabled = settings.coingecko_enabled
        self._api_key = settings.coingecko_api_key
        self._client = CoinGeckoAPI()

    async def is_available(self) -> bool:
        """Check if CoinGecko is enabled.

        Returns:
            True if enabled, False otherwise.
        """
        return self._enabled

    async def get_price(self, symbol: str) -> Decimal:
        """Get the current cryptocurrency price from CoinGecko.

        Args:
            symbol: The cryptocurrency symbol or ID (e.g., "bitcoin", "eth")

        Returns:
            The current price in USD.

        Raises:
            ValueError: If the price cannot be parsed.
            Exception: If the price cannot be retrieved.
        """
        logger.debug("Fetching CoinGecko price", symbol=symbol)

        coin_id = SYMBOL_TO_ID.get(symbol.lower(), symbol.lower())

        # pycoingecko is synchronous, run in thread pool
        data = await asyncio.to_thread(
            self._client.get_price,
            ids=coin_id,
            vs_currencies="usd",
        )

        if not data or coin_id not in data:
            raise Exception(f"No price data found for {symbol} (id={coin_id}) from CoinGecko")

        raw_price = data[coin_id].get("usd")
        if raw_price is None:
            raise Exception(f"No USD price found for {symbol} from CoinGecko")

        try:
            price = Decimal(str(raw_price))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid price value for {symbol}: {raw_price}") from exc

        logger.debug("CoinGecko price fetched", symbol=symbol, price=str(price))
        return price
