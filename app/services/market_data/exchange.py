"""Exchange rate service for currency conversion."""

from decimal import Decimal, InvalidOperation

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.exchangerate-api.com/v4/latest"


class ExchangeRateService:
    """Service for fetching currency exchange rates."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        """Initialize the exchange rate service.

        Args:
            base_url: The base URL for the exchange rate API.
        """
        self._base_url = base_url

    async def get_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Get the exchange rate from one currency to another.

        Args:
            from_currency: The source currency code (e.g., "EUR")
            to_currency: The target currency code (e.g., "USD")

        Returns:
            The exchange rate as a Decimal.

        Raises:
            ValueError: If the rate cannot be parsed.
            Exception: If the rate cannot be retrieved.
        """
        if from_currency.upper() == to_currency.upper():
            return Decimal("1")

        logger.debug(
            "Fetching exchange rate",
            from_currency=from_currency,
            to_currency=to_currency,
        )

        url = f"{self._base_url}/{from_currency.upper()}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        rates = data.get("rates", {})
        raw_rate = rates.get(to_currency.upper())

        if raw_rate is None:
            raise Exception(f"Exchange rate not found for {from_currency} to {to_currency}")

        try:
            rate = Decimal(str(raw_rate))
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid exchange rate value for {from_currency} to {to_currency}: {raw_rate}"
            ) from exc

        logger.debug(
            "Exchange rate fetched",
            from_currency=from_currency,
            to_currency=to_currency,
            rate=str(rate),
        )
        return rate

    async def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        """Convert an amount from one currency to another.

        Args:
            amount: The amount to convert.
            from_currency: The source currency code.
            to_currency: The target currency code.

        Returns:
            The converted amount.
        """
        rate = await self.get_rate(from_currency, to_currency)
        return amount * rate
