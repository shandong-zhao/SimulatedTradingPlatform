"""CLI interface for the simulated trading platform using Typer and Rich."""

import asyncio
from decimal import Decimal

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionLocal
from app.models import Account
from app.services.market_data.resolver import PriceResolver
from app.services.portfolio.portfolio import PortfolioService
from app.services.trading.execution import TradingExecutionService
from app.services.trading.quote import QuoteService

app = typer.Typer(
    name="trading-cli",
    help="Simulated Trading Platform CLI",
    rich_markup_mode="rich",
)
console = Console()


def _ensure_logging() -> None:
    """Configure logging on first use."""
    configure_logging()


logger = get_logger(__name__)


async def _get_first_account(session: AsyncSession) -> Account:
    """Get the first (and typically only) account."""
    result = await session.execute(select(Account).limit(1))
    account = result.scalar_one_or_none()
    if account is None:
        raise ValueError("No account found. Run the API server first to seed the database.")
    return account


def _run_async(coro):
    """Run an async coroutine and return its result."""
    return asyncio.run(coro)


def _format_money(value: Decimal) -> str:
    """Format a decimal as USD currency."""
    return f"${value:,.2f}"


def _format_quantity(value: Decimal) -> str:
    """Format quantity with appropriate precision."""
    if value == value.to_integral_value():
        return f"{int(value)}"
    return f"{value:.8f}"


# ------------------------------------------------------------------
# Portfolio Command
# ------------------------------------------------------------------


@app.command(name="portfolio")
def portfolio_command():
    """Show full portfolio summary with holdings and returns."""

    async def _portfolio():
        async with AsyncSessionLocal() as session:
            account = await _get_first_account(session)
            account_id = account.id

            service = PortfolioService()
            summary = await service.get_portfolio(account_id, session)

            # Header
            console.print(
                Panel.fit(
                    f"[bold green]Portfolio Summary[/bold green]\n"
                    f"Account ID: {account_id}\n"
                    f"Cash Balance: [bold]{_format_money(summary.cash_balance)}[/bold]",
                    title="💼 Portfolio",
                    border_style="green",
                )
            )

            # Stock holdings table
            if summary.stock_holdings:
                stock_table = Table(
                    title="Stock Holdings",
                    box=box.ROUNDED,
                    show_header=True,
                    header_style="bold magenta",
                )
                stock_table.add_column("Symbol", style="cyan")
                stock_table.add_column("Exchange", style="dim")
                stock_table.add_column("Qty", justify="right")
                stock_table.add_column("Avg Cost", justify="right")
                stock_table.add_column("Current", justify="right")
                stock_table.add_column("Value", justify="right")
                stock_table.add_column("PnL", justify="right")
                stock_table.add_column("Return %", justify="right")

                for h in summary.stock_holdings:
                    pnl_color = "green" if h.unrealized_pnl >= 0 else "red"
                    ret_color = "green" if h.return_pct >= 0 else "red"
                    stock_table.add_row(
                        h.symbol,
                        h.exchange,
                        _format_quantity(h.quantity),
                        _format_money(h.avg_cost_basis),
                        _format_money(h.current_price),
                        _format_money(h.current_value),
                        f"[{pnl_color}]{_format_money(h.unrealized_pnl)}[/{pnl_color}]",
                        f"[{ret_color}]{h.return_pct:.2f}%[/{ret_color}]",
                    )
                console.print(stock_table)
            else:
                console.print("[dim]No stock holdings.[/dim]\n")

            # Crypto holdings table
            if summary.crypto_holdings:
                crypto_table = Table(
                    title="Crypto Holdings",
                    box=box.ROUNDED,
                    show_header=True,
                    header_style="bold magenta",
                )
                crypto_table.add_column("Symbol", style="cyan")
                crypto_table.add_column("Qty", justify="right")
                crypto_table.add_column("Avg Cost", justify="right")
                crypto_table.add_column("Current", justify="right")
                crypto_table.add_column("Value", justify="right")
                crypto_table.add_column("PnL", justify="right")
                crypto_table.add_column("Return %", justify="right")

                for h in summary.crypto_holdings:
                    pnl_color = "green" if h.unrealized_pnl >= 0 else "red"
                    ret_color = "green" if h.return_pct >= 0 else "red"
                    crypto_table.add_row(
                        h.symbol,
                        _format_quantity(h.quantity),
                        _format_money(h.avg_cost_basis),
                        _format_money(h.current_price),
                        _format_money(h.current_value),
                        f"[{pnl_color}]{_format_money(h.unrealized_pnl)}[/{pnl_color}]",
                        f"[{ret_color}]{h.return_pct:.2f}%[/{ret_color}]",
                    )
                console.print(crypto_table)
            else:
                console.print("[dim]No crypto holdings.[/dim]\n")

            # Totals
            pnl_color = "green" if summary.total_unrealized_pnl >= 0 else "red"
            ret_color = "green" if summary.total_return_pct >= 0 else "red"
            console.print(
                Panel.fit(
                    f"Total Stock Value:   {_format_money(summary.total_stock_value)}\n"
                    f"Total Crypto Value:  {_format_money(summary.total_crypto_value)}\n"
                    f"Total Holdings:      [bold]{_format_money(summary.total_holdings_value)}[/bold]\n"
                    f"Total Portfolio:     [bold green]{_format_money(summary.total_value)}[/bold green]\n"
                    f"Total Invested:      {_format_money(summary.total_invested)}\n"
                    f"Unrealized PnL:      [{pnl_color}]{_format_money(summary.total_unrealized_pnl)}[/{pnl_color}]\n"
                    f"Total Return:        [{ret_color}]{summary.total_return_pct:.2f}%[/{ret_color}]",
                    title="📊 Totals",
                    border_style="blue",
                )
            )

    try:
        _run_async(_portfolio())
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# Quote Command
# ------------------------------------------------------------------


@app.command(name="quote")
def quote_command(
    symbol: str = typer.Argument(..., help="Asset symbol (e.g., AAPL, bitcoin)"),
):
    """Quick price lookup for a stock or crypto symbol."""

    async def _quote():
        resolver = PriceResolver()
        price = await resolver.get_price(symbol)

        console.print(
            Panel.fit(
                f"[bold cyan]{symbol.upper()}[/bold cyan]\n"
                f"Current Price: [bold green]{_format_money(price)}[/bold green]",
                title="💰 Price Quote",
                border_style="cyan",
            )
        )

    try:
        _run_async(_quote())
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# Buy Command
# ------------------------------------------------------------------


@app.command(name="buy")
def buy_command(
    symbol: str | None = typer.Option(None, help="Asset symbol"),
    exchange: str | None = typer.Option(None, help="Exchange code (e.g., NASDAQ, BINANCE)"),
    currency: str | None = typer.Option(None, help="Currency code (e.g., USD, GBP)"),
    asset_type: str | None = typer.Option(None, help="Asset type: stock or crypto"),
    usd_amount: str | None = typer.Option(None, help="Amount in USD to invest"),
):
    """Interactive buy command. Prompts for missing fields and asks for confirmation."""

    async def _buy():
        nonlocal symbol, exchange, currency, asset_type, usd_amount
        async with AsyncSessionLocal() as session:
            account = await _get_first_account(session)
            account_id = account.id

            # Interactive prompts for missing values
            if not symbol:
                symbol = Prompt.ask("[bold]Symbol[/bold]", default="AAPL")
            if not exchange:
                exchange = Prompt.ask("[bold]Exchange[/bold]", default="NASDAQ")
            if not currency:
                currency = Prompt.ask("[bold]Currency[/bold]", default="USD")
            if not asset_type:
                asset_type = Prompt.ask(
                    "[bold]Asset type[/bold]",
                    choices=["stock", "crypto"],
                    default="stock",
                )
            if not usd_amount:
                usd_amount = Prompt.ask("[bold]USD amount to invest[/bold]", default="1000")

            try:
                usd_amount_dec = Decimal(str(usd_amount))
            except Exception:
                console.print("[bold red]Invalid USD amount.[/bold red]")
                raise typer.Exit(1)

            # Generate quote
            quote_service = QuoteService()
            quote = await quote_service.generate_buy_quote(
                symbol=symbol,
                exchange=exchange,
                currency=currency,
                usd_amount=usd_amount_dec,
                asset_type=asset_type,
            )

            # Display preview
            console.print(
                Panel.fit(
                    f"Symbol:       [bold]{quote.symbol}[/bold]\n"
                    f"Exchange:     {quote.exchange}\n"
                    f"Asset Type:   {quote.asset_type}\n"
                    f"Price/Unit:   {_format_money(quote.usd_price_per_unit)} USD\n"
                    f"Quantity:     {_format_quantity(quote.quantity)}\n"
                    f"Total Value:  [bold]{_format_money(quote.total_usd_value)}[/bold]\n"
                    f"Fees:         {_format_money(quote.estimated_fees)}",
                    title="🛒 Buy Preview",
                    border_style="yellow",
                )
            )

            # Confirmation
            if not Confirm.ask("[bold]Confirm buy?[/bold]", default=True):
                console.print("[dim]Buy cancelled.[/dim]")
                return

            # Execute two-step flow: create pending then confirm
            execution_service = TradingExecutionService()
            pending_tx = await execution_service.create_pending_buy(
                account_id=account_id,
                quote=quote,
                db_session=session,
            )
            confirmed_tx = await execution_service.confirm_buy(
                transaction_id=pending_tx.id,
                db_session=session,
            )

            console.print(
                Panel.fit(
                    f"[bold green]Buy executed successfully![/bold green]\n"
                    f"Transaction ID: {confirmed_tx.id}\n"
                    f"Symbol:         {confirmed_tx.symbol}\n"
                    f"Quantity:       {_format_quantity(confirmed_tx.quantity)}\n"
                    f"Total Value:    {_format_money(confirmed_tx.total_usd_value)}\n"
                    f"Status:         [bold green]{confirmed_tx.status}[/bold green]",
                    title="✅ Buy Confirmed",
                    border_style="green",
                )
            )

    try:
        _run_async(_buy())
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        logger.error("Buy command failed", error=str(exc))
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# Sell Command
# ------------------------------------------------------------------


@app.command(name="sell")
def sell_command(
    symbol: str | None = typer.Option(None, help="Asset symbol"),
    exchange: str | None = typer.Option(None, help="Exchange code"),
    currency: str | None = typer.Option(None, help="Currency code"),
    asset_type: str | None = typer.Option(None, help="Asset type: stock or crypto"),
    quantity: str | None = typer.Option(None, help="Quantity to sell"),
):
    """Interactive sell command. Prompts for missing fields and asks for confirmation."""

    async def _sell():
        nonlocal symbol, exchange, currency, asset_type, quantity
        async with AsyncSessionLocal() as session:
            account = await _get_first_account(session)
            account_id = account.id

            # Interactive prompts for missing values
            if not symbol:
                symbol = Prompt.ask("[bold]Symbol[/bold]", default="AAPL")
            if not exchange:
                exchange = Prompt.ask("[bold]Exchange[/bold]", default="NASDAQ")
            if not currency:
                currency = Prompt.ask("[bold]Currency[/bold]", default="USD")
            if not asset_type:
                asset_type = Prompt.ask(
                    "[bold]Asset type[/bold]",
                    choices=["stock", "crypto"],
                    default="stock",
                )
            if not quantity:
                quantity = Prompt.ask("[bold]Quantity to sell[/bold]", default="10")

            try:
                quantity_dec = Decimal(str(quantity))
            except Exception:
                console.print("[bold red]Invalid quantity.[/bold red]")
                raise typer.Exit(1)

            # Generate quote
            quote_service = QuoteService()
            quote = await quote_service.generate_sell_quote(
                account_id=account_id,
                symbol=symbol,
                exchange=exchange,
                currency=currency,
                quantity=quantity_dec,
                asset_type=asset_type,
                db_session=session,
            )

            # Display preview
            pnl_color = "green" if quote.unrealized_pnl >= 0 else "red"
            console.print(
                Panel.fit(
                    f"Symbol:         [bold]{quote.symbol}[/bold]\n"
                    f"Exchange:       {quote.exchange}\n"
                    f"Asset Type:     {quote.asset_type}\n"
                    f"Price/Unit:     {_format_money(quote.usd_price_per_unit)} USD\n"
                    f"Quantity:       {_format_quantity(quote.quantity)}\n"
                    f"Holding Qty:    {_format_quantity(quote.holding_quantity)}\n"
                    f"Avg Cost:       {_format_money(quote.avg_cost_basis)}\n"
                    f"Total Value:    [bold]{_format_money(quote.total_usd_value)}[/bold]\n"
                    f"Unrealized PnL: [{pnl_color}]{_format_money(quote.unrealized_pnl)}[/{pnl_color}]\n"
                    f"Fees:           {_format_money(quote.estimated_fees)}",
                    title="🛒 Sell Preview",
                    border_style="yellow",
                )
            )

            # Confirmation
            if not Confirm.ask("[bold]Confirm sell?[/bold]", default=True):
                console.print("[dim]Sell cancelled.[/dim]")
                return

            # Execute two-step flow: create pending then confirm
            execution_service = TradingExecutionService()
            pending_tx = await execution_service.create_pending_sell(
                account_id=account_id,
                quote=quote,
                db_session=session,
            )
            confirmed_tx = await execution_service.confirm_sell(
                transaction_id=pending_tx.id,
                db_session=session,
            )

            console.print(
                Panel.fit(
                    f"[bold green]Sell executed successfully![/bold green]\n"
                    f"Transaction ID: {confirmed_tx.id}\n"
                    f"Symbol:         {confirmed_tx.symbol}\n"
                    f"Quantity:       {_format_quantity(confirmed_tx.quantity)}\n"
                    f"Total Value:    {_format_money(confirmed_tx.total_usd_value)}\n"
                    f"Status:         [bold green]{confirmed_tx.status}[/bold green]",
                    title="✅ Sell Confirmed",
                    border_style="green",
                )
            )

    try:
        _run_async(_sell())
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        logger.error("Sell command failed", error=str(exc))
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# History Command
# ------------------------------------------------------------------


@app.command(name="history")
def history_command(
    limit: int = typer.Option(20, help="Number of transactions to show"),
):
    """Show transaction history."""

    async def _history():
        async with AsyncSessionLocal() as session:
            account = await _get_first_account(session)
            account_id = account.id

            service = PortfolioService()
            transactions = await service.get_transaction_history(
                account_id=account_id,
                db_session=session,
                limit=limit,
                offset=0,
            )

            if not transactions:
                console.print("[dim]No transactions found.[/dim]")
                return

            table = Table(
                title=f"Transaction History (last {len(transactions)})",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Type", style="cyan")
            table.add_column("Asset", style="dim")
            table.add_column("Symbol", style="bold")
            table.add_column("Qty", justify="right")
            table.add_column("Price", justify="right")
            table.add_column("Total", justify="right")
            table.add_column("Status", justify="center")
            table.add_column("Time", style="dim")

            for tx in transactions:
                type_color = "green" if tx.type == "buy" else "red"
                status_color = {
                    "CONFIRMED": "green",
                    "PENDING": "yellow",
                    "CANCELLED": "red",
                }.get(tx.status, "white")

                table.add_row(
                    f"[{type_color}]{tx.type.upper()}[/{type_color}]",
                    tx.asset_type,
                    tx.symbol,
                    _format_quantity(tx.quantity),
                    _format_money(tx.usd_price_per_unit),
                    _format_money(tx.total_usd_value),
                    f"[{status_color}]{tx.status}[/{status_color}]",
                    tx.timestamp.split("T")[0] if tx.timestamp else "",
                )

            console.print(table)

    try:
        _run_async(_history())
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main():
    """CLI entry point."""
    _ensure_logging()
    app()


if __name__ == "__main__":
    main()
