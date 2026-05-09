"""Tests for ExchangeRateService."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.market_data.exchange import ExchangeRateService


@pytest.mark.asyncio
class TestExchangeRateService:
    """Test ExchangeRateService with manual mocking."""

    async def test_get_rate_eur_to_usd(self):
        """Test fetching EUR to USD rate."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"USD": 1.085}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            rate = await service.get_rate("EUR", "USD")

        assert rate == Decimal("1.085")

    async def test_get_rate_gbp_to_usd(self):
        """Test fetching GBP to USD rate."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"USD": 1.27}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            rate = await service.get_rate("GBP", "USD")

        assert rate == Decimal("1.27")

    async def test_get_rate_jpy_to_usd(self):
        """Test fetching JPY to USD rate."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"USD": 0.0067}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            rate = await service.get_rate("JPY", "USD")

        assert rate == Decimal("0.0067")

    async def test_get_rate_same_currency_returns_one(self):
        """Test that same currency returns 1 without API call."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            rate = await service.get_rate("USD", "USD")

        assert rate == Decimal("1")
        mock_get.assert_not_called()

    async def test_get_rate_case_insensitive(self):
        """Test currency codes are case-insensitive."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"EUR": 0.92}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            rate = await service.get_rate("usd", "eur")

        assert rate == Decimal("0.92")
        mock_get.assert_called_once()
        # Verify the URL uses uppercase
        call_args = mock_get.call_args
        assert "USD" in str(call_args)

    async def test_get_rate_missing_rate_raises(self):
        """Test exception when target currency is missing."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"EUR": 0.92}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="Exchange rate not found"):
                await service.get_rate("USD", "ZZZ")

    async def test_get_rate_api_error_raises(self):
        """Test exception when API request fails."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("Network error")
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="Network error"):
                await service.get_rate("USD", "EUR")

    async def test_get_rate_invalid_rate_value_raises(self):
        """Test exception when rate value is invalid."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"EUR": "invalid"}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            with pytest.raises(ValueError, match="Invalid exchange rate"):
                await service.get_rate("USD", "EUR")

    async def test_convert(self):
        """Test currency conversion."""
        service = ExchangeRateService()

        with patch.object(service, "get_rate", return_value=Decimal("1.1")) as mock_rate:
            result = await service.convert(Decimal("100"), "EUR", "USD")

        mock_rate.assert_awaited_once_with("EUR", "USD")
        assert result == Decimal("110")

    async def test_convert_zero_amount(self):
        """Test conversion of zero amount."""
        service = ExchangeRateService()

        with patch.object(service, "get_rate", return_value=Decimal("1.1")) as mock_rate:
            result = await service.convert(Decimal("0"), "EUR", "USD")

        assert result == Decimal("0")

    async def test_convert_with_decimals(self):
        """Test conversion with fractional amounts."""
        service = ExchangeRateService()

        with patch.object(service, "get_rate", return_value=Decimal("0.85")) as mock_rate:
            result = await service.convert(Decimal("99.99"), "EUR", "USD")

        assert result == Decimal("84.9915")
