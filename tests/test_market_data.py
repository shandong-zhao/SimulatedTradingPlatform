"""Tests for market data services."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.market_data.base import MarketDataProvider
from app.services.market_data.coingecko import CoinGeckoProvider
from app.services.market_data.exchange import ExchangeRateService
from app.services.market_data.resolver import PriceResolver
from app.services.market_data.yahoo import YahooFinanceProvider


class FakeProvider(MarketDataProvider):
    """Fake provider for testing."""

    def __init__(self, price: Decimal | None = None, available: bool = True) -> None:
        """Initialize with optional price and availability."""
        self._price = price
        self._available = available

    async def get_price(self, symbol: str) -> Decimal:
        """Return the configured price or raise."""
        if self._price is None:
            raise Exception("No price configured")
        return self._price

    async def is_available(self) -> bool:
        """Return configured availability."""
        return self._available


@pytest.mark.asyncio
class TestYahooFinanceProvider:
    """Test YahooFinanceProvider."""

    async def test_get_price_success(self):
        """Test successful price fetch from Yahoo Finance."""
        provider = YahooFinanceProvider()
        mock_info = {"currentPrice": 150.25}

        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = mock_info
            mock_ticker_cls.return_value = mock_ticker

            price = await provider.get_price("AAPL")

        assert price == Decimal("150.25")

    async def test_get_price_fallback_keys(self):
        """Test price fetch with fallback keys."""
        provider = YahooFinanceProvider()
        mock_info = {"regularMarketPrice": 200.0}

        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = mock_info
            mock_ticker_cls.return_value = mock_ticker

            price = await provider.get_price("MSFT")

        assert price == Decimal("200.0")

    async def test_get_price_no_data(self):
        """Test price fetch when no price data exists."""
        provider = YahooFinanceProvider()
        mock_info = {}

        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = mock_info
            mock_ticker_cls.return_value = mock_ticker

            with pytest.raises(Exception, match="No price data found"):
                await provider.get_price("UNKNOWN")

    async def test_is_available(self):
        """Test availability check."""
        provider = YahooFinanceProvider()
        assert await provider.is_available() is True


@pytest.mark.asyncio
class TestCoinGeckoProvider:
    """Test CoinGeckoProvider."""

    async def test_get_price_success(self):
        """Test successful price fetch from CoinGecko."""
        provider = CoinGeckoProvider()

        with patch.object(
            provider._client,
            "get_price",
            return_value={"bitcoin": {"usd": 50000.0}},
        ):
            price = await provider.get_price("bitcoin")

        assert price == Decimal("50000.0")

    async def test_get_price_symbol_mapping(self):
        """Test price fetch with symbol mapping."""
        provider = CoinGeckoProvider()

        with patch.object(
            provider._client,
            "get_price",
            return_value={"ethereum": {"usd": 3000.5}},
        ):
            price = await provider.get_price("ETH")

        assert price == Decimal("3000.5")

    async def test_get_price_no_data(self):
        """Test price fetch when no data returned."""
        provider = CoinGeckoProvider()

        with (
            patch.object(provider._client, "get_price", return_value={}),
            pytest.raises(Exception, match="No price data found"),
        ):
            await provider.get_price("unknowncoin")

    async def test_is_available(self):
        """Test availability check."""
        provider = CoinGeckoProvider()
        assert await provider.is_available() is True


@pytest.mark.asyncio
class TestExchangeRateService:
    """Test ExchangeRateService."""

    async def test_get_rate_success(self):
        """Test successful rate fetch."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {"USD": 1.1}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            rate = await service.get_rate("EUR", "USD")

        assert rate == Decimal("1.1")

    async def test_get_rate_same_currency(self):
        """Test rate for same currency returns 1."""
        service = ExchangeRateService()
        rate = await service.get_rate("USD", "USD")
        assert rate == Decimal("1")

    async def test_get_rate_missing_rate(self):
        """Test rate fetch when target currency missing."""
        service = ExchangeRateService()

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"rates": {}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="Exchange rate not found"):
                await service.get_rate("EUR", "ZZZ")

    async def test_convert(self):
        """Test currency conversion."""
        service = ExchangeRateService()

        with patch.object(service, "get_rate", return_value=Decimal("1.1")) as mock_rate:
            result = await service.convert(Decimal("100"), "EUR", "USD")

        mock_rate.assert_awaited_once_with("EUR", "USD")
        assert result == Decimal("110")


@pytest.mark.asyncio
class TestPriceResolver:
    """Test PriceResolver."""

    async def test_get_price_stock_routes_to_yahoo(self):
        """Test stock symbol routes to Yahoo Finance."""
        resolver = PriceResolver()
        resolver.clear_cache()
        resolver._yahoo = FakeProvider(price=Decimal("150.0"))
        resolver._coingecko = FakeProvider(price=Decimal("0"))

        price = await resolver.get_price("AAPL")

        assert price == Decimal("150.0")

    async def test_get_price_crypto_routes_to_coingecko(self):
        """Test crypto symbol routes to CoinGecko."""
        resolver = PriceResolver()
        resolver.clear_cache()
        resolver._yahoo = FakeProvider(price=Decimal("0"))
        resolver._coingecko = FakeProvider(price=Decimal("50000.0"))

        price = await resolver.get_price("BTC")

        assert price == Decimal("50000.0")

    async def test_get_price_fallback(self):
        """Test fallback when primary provider fails."""
        resolver = PriceResolver()
        resolver.clear_cache()
        resolver._yahoo = FakeProvider(price=Decimal("150.0"))
        resolver._coingecko = FakeProvider(available=False)

        # BTC routes to coingecko first, but it's unavailable, so falls back to yahoo
        price = await resolver.get_price("BTC")

        assert price == Decimal("150.0")

    async def test_get_price_all_providers_fail(self):
        """Test exception when all providers fail."""
        resolver = PriceResolver()
        resolver.clear_cache()
        resolver._yahoo = FakeProvider(available=False)
        resolver._coingecko = FakeProvider(available=False)

        with pytest.raises(Exception, match="Unable to retrieve price"):
            await resolver.get_price("AAPL")

    async def test_caching(self):
        """Test that prices are cached."""
        resolver = PriceResolver()
        resolver.clear_cache()
        resolver._yahoo = FakeProvider(price=Decimal("150.0"))
        resolver._coingecko = FakeProvider(price=Decimal("0"))

        price1 = await resolver.get_price("AAPL")
        price2 = await resolver.get_price("AAPL")

        assert price1 == price2 == Decimal("150.0")

    async def test_is_crypto(self):
        """Test crypto detection."""
        resolver = PriceResolver()
        assert resolver._is_crypto("BTC") is True
        assert resolver._is_crypto("bitcoin") is True
        assert resolver._is_crypto("AAPL") is False
