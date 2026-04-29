"""Base class for market data providers."""

from abc import ABC, abstractmethod
from decimal import Decimal


class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    async def get_price(self, symbol: str) -> Decimal:
        """Get the current price for a symbol.

        Args:
            symbol: The asset symbol (e.g., "AAPL", "bitcoin")

        Returns:
            The current price in the provider's default currency.

        Raises:
            Exception: If the price cannot be retrieved.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available.

        Returns:
            True if the provider can serve requests, False otherwise.
        """
        ...
