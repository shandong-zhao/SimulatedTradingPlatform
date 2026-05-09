"""Tests for CLI commands."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


# ------------------------------------------------------------------
# Portfolio Command Tests
# ------------------------------------------------------------------


class TestPortfolioCommand:
    """Test portfolio CLI command."""

    @patch("app.cli.PortfolioService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_portfolio_empty(self, mock_session_class, mock_get_account, mock_portfolio_service):
        """Test portfolio command with no holdings."""
        from app.schemas.portfolio import PortfolioSummary

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        mock_summary = PortfolioSummary(
            account_id="acc-123",
            cash_balance=Decimal("100000.00"),
            stock_holdings=[],
            crypto_holdings=[],
            total_stock_value=Decimal("0"),
            total_crypto_value=Decimal("0"),
            total_holdings_value=Decimal("0"),
            total_value=Decimal("100000.00"),
            total_invested=Decimal("0"),
            total_unrealized_pnl=Decimal("0"),
            total_return_pct=Decimal("0"),
        )

        mock_service = MagicMock()
        mock_service.get_portfolio = AsyncMock(return_value=mock_summary)
        mock_portfolio_service.return_value = mock_service

        # Mock session context manager
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(app, ["portfolio"])

        assert result.exit_code == 0
        assert "Portfolio Summary" in result.output
        assert "100,000.00" in result.output or "$100,000.00" in result.output

    @patch("app.cli.PortfolioService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_portfolio_with_holdings(
        self, mock_session_class, mock_get_account, mock_portfolio_service
    ):
        """Test portfolio command with stock and crypto holdings."""
        from app.schemas.portfolio import CryptoHoldingDetail, PortfolioSummary, StockHoldingDetail

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        mock_summary = PortfolioSummary(
            account_id="acc-123",
            cash_balance=Decimal("85000.00"),
            stock_holdings=[
                StockHoldingDetail(
                    symbol="AAPL",
                    exchange="NASDAQ",
                    currency="USD",
                    quantity=Decimal("10"),
                    avg_cost_basis=Decimal("150.00"),
                    total_invested=Decimal("1500.00"),
                    current_price=Decimal("160.00"),
                    current_value=Decimal("1600.00"),
                    unrealized_pnl=Decimal("100.00"),
                    return_pct=Decimal("6.67"),
                ),
            ],
            crypto_holdings=[
                CryptoHoldingDetail(
                    symbol="BTC",
                    quantity=Decimal("0.1"),
                    avg_cost_basis=Decimal("50000.00"),
                    total_invested=Decimal("5000.00"),
                    current_price=Decimal("55000.00"),
                    current_value=Decimal("5500.00"),
                    unrealized_pnl=Decimal("500.00"),
                    return_pct=Decimal("10.00"),
                ),
            ],
            total_stock_value=Decimal("1600.00"),
            total_crypto_value=Decimal("5500.00"),
            total_holdings_value=Decimal("7100.00"),
            total_value=Decimal("92100.00"),
            total_invested=Decimal("6500.00"),
            total_unrealized_pnl=Decimal("600.00"),
            total_return_pct=Decimal("9.23"),
        )

        mock_service = MagicMock()
        mock_service.get_portfolio = AsyncMock(return_value=mock_summary)
        mock_portfolio_service.return_value = mock_service

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(app, ["portfolio"])

        assert result.exit_code == 0
        assert "AAPL" in result.output
        assert "BTC" in result.output


# ------------------------------------------------------------------
# Quote Command Tests
# ------------------------------------------------------------------


class TestQuoteCommand:
    """Test quote CLI command."""

    @patch("app.cli.PriceResolver")
    def test_quote_success(self, mock_resolver_class):
        """Test quote command with valid symbol."""
        mock_resolver = MagicMock()
        mock_resolver.get_price = AsyncMock(return_value=Decimal("150.00"))
        mock_resolver_class.return_value = mock_resolver

        result = runner.invoke(app, ["quote", "AAPL"])

        assert result.exit_code == 0
        assert "AAPL" in result.output
        assert "150.00" in result.output
        mock_resolver.get_price.assert_called_once_with("AAPL")

    @patch("app.cli.PriceResolver")
    def test_quote_error(self, mock_resolver_class):
        """Test quote command when price lookup fails."""
        mock_resolver = MagicMock()
        mock_resolver.get_price = AsyncMock(side_effect=Exception("API error"))
        mock_resolver_class.return_value = mock_resolver

        result = runner.invoke(app, ["quote", "INVALID"])

        assert result.exit_code == 1
        assert "API error" in result.output or "Error" in result.output


# ------------------------------------------------------------------
# Buy Command Tests
# ------------------------------------------------------------------


class TestBuyCommand:
    """Test buy CLI command."""

    @patch("app.cli.Confirm.ask")
    @patch("app.cli.TradingExecutionService")
    @patch("app.cli.QuoteService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_buy_success(
        self,
        mock_session_class,
        mock_get_account,
        mock_quote_service,
        mock_exec_service,
        mock_confirm,
    ):
        """Test successful buy command with all options."""
        from app.schemas.trading import BuyQuote

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        # Mock quote
        mock_quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        mock_qs = MagicMock()
        mock_qs.generate_buy_quote = AsyncMock(return_value=mock_quote)
        mock_quote_service.return_value = mock_qs

        # Mock execution
        mock_pending = MagicMock()
        mock_pending.id = "tx-pending-1"
        mock_confirmed = MagicMock()
        mock_confirmed.id = "tx-pending-1"
        mock_confirmed.symbol = "AAPL"
        mock_confirmed.quantity = Decimal("10")
        mock_confirmed.total_usd_value = Decimal("1500.00")
        mock_confirmed.status = "CONFIRMED"

        mock_es = MagicMock()
        mock_es.create_pending_buy = AsyncMock(return_value=mock_pending)
        mock_es.confirm_buy = AsyncMock(return_value=mock_confirmed)
        mock_exec_service.return_value = mock_es

        mock_confirm.return_value = True

        # Mock session context manager
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(
            app,
            [
                "buy",
                "--symbol",
                "AAPL",
                "--exchange",
                "NASDAQ",
                "--currency",
                "USD",
                "--asset-type",
                "stock",
                "--usd-amount",
                "1500",
            ],
        )

        assert result.exit_code == 0
        mock_qs.generate_buy_quote.assert_called_once()
        mock_es.create_pending_buy.assert_called_once()
        mock_es.confirm_buy.assert_called_once()

    @patch("app.cli.Confirm.ask")
    @patch("app.cli.QuoteService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_buy_cancelled(
        self, mock_session_class, mock_get_account, mock_quote_service, mock_confirm
    ):
        """Test buy command when user cancels."""
        from app.schemas.trading import BuyQuote

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        mock_quote = BuyQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("10"),
            total_usd_value=Decimal("1500.00"),
            estimated_fees=Decimal("0"),
            preview=False,
        )

        mock_qs = MagicMock()
        mock_qs.generate_buy_quote = AsyncMock(return_value=mock_quote)
        mock_quote_service.return_value = mock_qs

        mock_confirm.return_value = False

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(
            app,
            [
                "buy",
                "--symbol",
                "AAPL",
                "--exchange",
                "NASDAQ",
                "--currency",
                "USD",
                "--asset-type",
                "stock",
                "--usd-amount",
                "1500",
            ],
        )

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower() or "Cancelled" in result.output


# ------------------------------------------------------------------
# Sell Command Tests
# ------------------------------------------------------------------


class TestSellCommand:
    """Test sell CLI command."""

    @patch("app.cli.Confirm.ask")
    @patch("app.cli.TradingExecutionService")
    @patch("app.cli.QuoteService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_sell_success(
        self,
        mock_session_class,
        mock_get_account,
        mock_quote_service,
        mock_exec_service,
        mock_confirm,
    ):
        """Test successful sell command with all options."""
        from app.schemas.trading import SellQuote

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        mock_quote = SellQuote(
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            asset_type="stock",
            price_per_unit=Decimal("150.00"),
            usd_price_per_unit=Decimal("150.00"),
            exchange_rate=Decimal("1"),
            quantity=Decimal("5"),
            total_usd_value=Decimal("750.00"),
            estimated_fees=Decimal("0"),
            holding_quantity=Decimal("10"),
            avg_cost_basis=Decimal("140.00"),
            unrealized_pnl=Decimal("50.00"),
            preview=False,
        )

        mock_qs = MagicMock()
        mock_qs.generate_sell_quote = AsyncMock(return_value=mock_quote)
        mock_quote_service.return_value = mock_qs

        mock_pending = MagicMock()
        mock_pending.id = "tx-sell-1"
        mock_confirmed = MagicMock()
        mock_confirmed.id = "tx-sell-1"
        mock_confirmed.symbol = "AAPL"
        mock_confirmed.quantity = Decimal("5")
        mock_confirmed.total_usd_value = Decimal("750.00")
        mock_confirmed.status = "CONFIRMED"

        mock_es = MagicMock()
        mock_es.create_pending_sell = AsyncMock(return_value=mock_pending)
        mock_es.confirm_sell = AsyncMock(return_value=mock_confirmed)
        mock_exec_service.return_value = mock_es

        mock_confirm.return_value = True

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(
            app,
            [
                "sell",
                "--symbol",
                "AAPL",
                "--exchange",
                "NASDAQ",
                "--currency",
                "USD",
                "--asset-type",
                "stock",
                "--quantity",
                "5",
            ],
        )

        assert result.exit_code == 0
        mock_qs.generate_sell_quote.assert_called_once()
        mock_es.create_pending_sell.assert_called_once()
        mock_es.confirm_sell.assert_called_once()


# ------------------------------------------------------------------
# History Command Tests
# ------------------------------------------------------------------


class TestHistoryCommand:
    """Test history CLI command."""

    @patch("app.cli.PortfolioService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_history_empty(self, mock_session_class, mock_get_account, mock_portfolio_service):
        """Test history command with no transactions."""
        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        mock_service = MagicMock()
        mock_service.get_transaction_history = AsyncMock(return_value=[])
        mock_portfolio_service.return_value = mock_service

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(app, ["history"])

        assert result.exit_code == 0
        assert "No transactions" in result.output or "No transactions found" in result.output

    @patch("app.cli.PortfolioService")
    @patch("app.cli._get_first_account")
    @patch("app.cli.AsyncSessionLocal")
    def test_history_with_transactions(
        self, mock_session_class, mock_get_account, mock_portfolio_service
    ):
        """Test history command with transactions."""
        from app.schemas.portfolio import TransactionHistoryItem

        mock_account = MagicMock()
        mock_account.id = "acc-123"
        mock_get_account.return_value = mock_account

        mock_txs = [
            TransactionHistoryItem(
                id="tx-1",
                type="buy",
                asset_type="stock",
                symbol="AAPL",
                exchange="NASDAQ",
                quantity=Decimal("10"),
                price_per_unit=Decimal("150.00"),
                currency="USD",
                exchange_rate=Decimal("1"),
                usd_price_per_unit=Decimal("150.00"),
                total_usd_value=Decimal("1500.00"),
                fees=Decimal("0"),
                status="CONFIRMED",
                timestamp="2024-01-15T10:30:00",
            ),
            TransactionHistoryItem(
                id="tx-2",
                type="sell",
                asset_type="crypto",
                symbol="BTC",
                exchange="BINANCE",
                quantity=Decimal("0.5"),
                price_per_unit=Decimal("50000.00"),
                currency="USD",
                exchange_rate=Decimal("1"),
                usd_price_per_unit=Decimal("50000.00"),
                total_usd_value=Decimal("25000.00"),
                fees=Decimal("0"),
                status="CONFIRMED",
                timestamp="2024-01-16T14:00:00",
            ),
        ]

        mock_service = MagicMock()
        mock_service.get_transaction_history = AsyncMock(return_value=mock_txs)
        mock_portfolio_service.return_value = mock_service

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(app, ["history"])

        assert result.exit_code == 0
        assert "AAPL" in result.output
        assert "BTC" in result.output
