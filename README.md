# Simulated Trading Platform

A simulated trading platform for stocks and cryptocurrencies with real-time market data integration.

## Features

- **Real Market Data**: Live prices from Yahoo Finance (stocks) and CoinGecko (crypto)
- **Portfolio Management**: Track holdings, calculate returns, view transaction history
- **Trading Engine**: Buy/sell with USD amount or quantity, automatic cost basis tracking
- **REST API**: Full FastAPI-powered API with automatic documentation
- **CLI Interface**: Interactive command-line interface for quick trading
- **Exchange Rate Support**: Automatic currency conversion for non-US exchanges

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: SQLite + SQLAlchemy + Alembic
- **Validation**: Pydantic v2
- **Market Data**: Yahoo Finance, CoinGecko
- **CLI**: Typer + Rich
- **Testing**: pytest + pytest-cov + httpx
- **Linting**: Ruff + Black
- **Type Checking**: mypy

## Quick Start

### Prerequisites

- Python 3.11+
- pip or uv

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd simulated-trading-platform
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Start the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Usage

Once the server is running, you can access:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Health Check

```bash
curl http://localhost:8000/health
```

### Portfolio

```bash
# Get full portfolio overview
curl http://localhost:8000/api/portfolio

# Get holdings list
curl http://localhost:8000/api/portfolio/holdings

# Get transaction history
curl http://localhost:8000/api/portfolio/transactions
```

### Market Data

```bash
# Get current price for a stock
curl http://localhost:8000/api/market/price/AAPL

# Get current price for crypto (use crypto asset type)
curl "http://localhost:8000/api/market/price/BTC?asset_type=crypto"

# Get exchange rate
curl http://localhost:8000/api/market/rates/GBP/USD
```

### Trading

#### Buy Flow

```bash
# Step 1: Get a buy quote
curl -X POST http://localhost:8000/api/trading/quote \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "exchange": "NASDAQ",
    "currency": "USD",
    "asset_type": "stock",
    "usd_amount": "1500.00"
  }'

# Step 2: Preview the buy (creates PENDING transaction)
curl -X POST http://localhost:8000/api/trading/buy \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "<your-account-id>",
    "symbol": "AAPL",
    "exchange": "NASDAQ",
    "currency": "USD",
    "usd_amount": "1500.00",
    "asset_type": "stock"
  }'

# Step 3: Confirm the buy (executes the trade)
curl -X POST http://localhost:8000/api/trading/buy/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "<pending-transaction-id>"
  }'
```

#### Sell Flow

```bash
# Step 1: Preview the sell (creates PENDING transaction)
curl -X POST http://localhost:8000/api/trading/sell \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "<your-account-id>",
    "symbol": "AAPL",
    "exchange": "NASDAQ",
    "currency": "USD",
    "quantity": "5",
    "asset_type": "stock"
  }'

# Step 2: Confirm the sell (executes the trade)
curl -X POST http://localhost:8000/api/trading/sell/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "<pending-transaction-id>"
  }'
```

## CLI Usage

The CLI is available as `trading-cli` after installation.

```bash
# Show full portfolio
trading-cli portfolio

# Quick price lookup
trading-cli quote --symbol BTC --asset-type crypto

# Transaction history
trading-cli history
```

### Interactive Buy

```bash
# With all arguments
trading-cli buy \
  --symbol AAPL \
  --exchange NASDAQ \
  --currency USD \
  --asset-type stock \
  --usd-amount 1000

# Interactive mode (prompts for missing fields)
trading-cli buy --symbol AAPL --usd-amount 500
```

### Interactive Sell

```bash
# With all arguments
trading-cli sell \
  --symbol AAPL \
  --exchange NASDAQ \
  --currency USD \
  --asset-type stock \
  --quantity 5

# Interactive mode
trading-cli sell --symbol BTC --quantity 0.5
```

## Supported Exchanges

| Exchange | Type | Default Currency |
|----------|------|------------------|
| NASDAQ | Stock | USD |
| NYSE | Stock | USD |
| LSE | Stock | GBP |
| TSE | Stock | JPY |
| BINANCE | Crypto | USD |
| COINBASE | Crypto | USD |
| KRAKEN | Crypto | USD |

## Supported Cryptocurrencies

BTC, ETH, ADA, DOT, SOL, XRP, DOGE, LINK, UNI, LTC

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐
│   CLI       │────▶│   FastAPI   │────▶│      Trading Services       │
│  (Typer)    │     │   Routes    │     │  - QuoteService             │
└─────────────┘     └─────────────┘     │  - TradingExecutionService  │
                                        │  - PortfolioService         │
                                        └─────────────────────────────┘
                                                  │
                        ┌─────────────────────────┼─────────────────────────┐
                        ▼                         ▼                         ▼
              ┌─────────────────┐      ┌─────────────────┐      ┌───────────────┐
              │ Yahoo Finance   │      │ CoinGecko       │      │ Exchange Rate │
              │ Provider        │      │ Provider        │      │ Service       │
              └─────────────────┘      └─────────────────┘      └───────────────┘
                        │                         │
                        └─────────────────────────┘
                                                  │
                                                  ▼
                                        ┌─────────────────┐
                                        │   SQLite DB     │
                                        │  (SQLAlchemy)   │
                                        └─────────────────┘
```

## Configuration

All configuration is managed through environment variables. Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | Application environment |
| `DEBUG` | `true` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite:///./trading.db` | Database connection string |
| `DEFAULT_CASH_BALANCE` | `100000.00` | Starting cash balance for new accounts |
| `MARKET_DATA_CACHE_TTL` | `300` | Price cache TTL in seconds |
| `YFINANCE_ENABLED` | `true` | Enable Yahoo Finance provider |
| `COINGECKO_ENABLED` | `true` | Enable CoinGecko provider |
| `COINGECKO_API_KEY` | *(empty)* | API key for CoinGecko paid tier |

## Development

### Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=app --cov-report=html
```

### Code Formatting

```bash
ruff check . --fix
black .
```

### Type Checking

```bash
mypy app
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

## Troubleshooting

### Tests fail with structlog error

If you see `AttributeError: 'PrintLogger' object has no attribute 'disabled'`, this is a test environment issue. The test suite patches `app.core.logging.configure_logging` to prevent this. If running tests individually fails, run the full suite:

```bash
pytest tests/ -o addopts=""
```

### Market data API returns no price

If Yahoo Finance or CoinGecko is temporarily unavailable, the system has fallback behavior:
- Stock prices: Falls back to cached values (5-minute TTL)
- Crypto prices: Falls back to cached values
- If all providers fail, the trading engine returns an error with the last known price if available

### Database locked error

The project uses `aiosqlite` (async SQLite driver) which handles concurrent access. If you see "database locked" errors:
1. Check that only one process is accessing `trading.db`
2. For tests, the in-memory database is used automatically

### Pre-commit hooks fail

If pre-commit hooks fail on commit:

```bash
# Run manually to see what's wrong
ruff check . --fix
black .

# Skip hooks temporarily (not recommended for production)
git commit --no-verify -m "your message"
```

## Project Structure

```
├── alembic/              # Database migrations
├── app/
│   ├── api/              # API routes and middleware
│   ├── cli.py            # CLI interface
│   ├── core/             # Configuration and logging
│   ├── db/               # Database setup and seeding
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   └── main.py           # FastAPI entry point
├── tests/                # Test suite
├── .env.example          # Example environment variables
├── .pre-commit-config.yaml
├── alembic.ini
├── pyproject.toml
└── README.md
```

## License

MIT
