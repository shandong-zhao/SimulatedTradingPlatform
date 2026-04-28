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

### API Documentation

Once the server is running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Health Check

```bash
curl http://localhost:8000/health
```

## Development

### Running Tests

```bash
pytest
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

## Configuration

All configuration is managed through environment variables. See `.env` for available options.

Key variables:
- `APP_ENV` - Environment (development/production)
- `DEBUG` - Enable debug mode
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `DATABASE_URL` - Database connection string
- `DEFAULT_CASH_BALANCE` - Starting cash balance

## Architecture

The project follows a layered architecture:
- `app/api/` - API routes and middleware
- `app/core/` - Configuration and logging
- `app/db/` - Database models and migrations
- `app/models/` - SQLAlchemy models
- `app/schemas/` - Pydantic schemas
- `app/services/` - Business logic
- `app/utils/` - Utility functions

## License

MIT
