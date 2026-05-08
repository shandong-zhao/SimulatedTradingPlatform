# Simulated Trading Platform - Implementation TODO

## Phase 1: Project Foundation
- [x] 1.1 Initialize Python project with `pyproject.toml` (Poetry or setuptools)
- [x] 1.2 Create virtual environment and install core dependencies
- [x] 1.3 Set up project directory structure (`app/`, `tests/`, `config/`, etc.)
- [x] 1.4 Configure environment variables (`.env` + `python-dotenv`)
- [x] 1.5 Add FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic to dependencies
- [x] 1.6 Create basic FastAPI application entry point (`main.py`)
- [x] 1.7 Set up health check endpoint (`GET /health`)
- [x] 1.8 Configure logging (structured JSON logging)
- [x] 1.9 Add basic error handling middleware
- [x] 1.10 Write initial `README.md` with setup instructions

## Phase 2: Database & Data Models
- [x] 2.1 Configure SQLAlchemy with SQLite database
- [x] 2.2 Set up Alembic for database migrations
- [x] 2.3 Create `Account` model (id, cash_balance, created_at, updated_at)
- [x] 2.4 Create `StockHolding` model (id, account_id, symbol, exchange, currency, quantity, avg_cost_basis, total_invested)
- [x] 2.5 Create `CryptoHolding` model (id, account_id, symbol, quantity, avg_cost_basis, total_invested)
- [x] 2.6 Create `Transaction` model (id, account_id, type, asset_type, symbol, exchange, quantity, price_per_unit, currency, exchange_rate, usd_price_per_unit, total_usd_value, fees, timestamp, status)
- [x] 2.7 Create initial Alembic migration
- [x] 2.8 Seed initial account with default cash balance ($100,000)
- [x] 2.9 Write database fixture/setup utility
- [x] 2.10 Add database session dependency injection for FastAPI

## Phase 3: Market Data Integration
- [x] 3.1 Create `MarketDataProvider` abstract base class
- [x] 3.2 Implement Yahoo Finance client for stock prices (`yfinance` library)
- [x] 3.3 Implement CoinGecko client for crypto prices (`pycoingecko` library)
- [x] 3.4 Implement exchange rate service (USD conversion for non-US exchanges)
- [x] 3.5 Create unified price resolver that routes to correct provider
- [x] 3.6 Add in-memory caching for prices (5-minute TTL using `cachetools`)
- [x] 3.7 Handle API errors and rate limiting with retries
- [x] 3.8 Add fallback behavior when APIs are unavailable
- [x] 3.9 Write unit tests for market data clients (mock API responses)
- [x] 3.10 Add API endpoints for market data (`GET /api/market/price/:symbol`, `GET /api/market/rates/:from/:to`)

## Phase 4: Trading Engine Core
- [x] 4.1 Create `QuoteService` to calculate shares from USD amount
- [x] 4.2 Implement buy quote generation (fetch price, convert to USD, calculate quantity)
- [x] 4.3 Implement sell quote generation (validate holdings, calculate proceeds)
- [x] 4.4 Create transaction preview model (what-if scenario)
- [x] 4.5 Implement buy execution flow (deduct cash, add/update holdings, record transaction)
- [x] 4.6 Implement sell execution flow (remove/reduce holdings, add cash, record transaction)
- [x] 4.7 Implement average cost basis updates on buy
- [x] 4.8 Implement average cost basis updates on partial sell
- [x] 4.9 Add transaction status tracking (PENDING → CONFIRMED/CANCELLED)
- [x] 4.10 Write unit tests for trading engine calculations
- [x] 4.11 Write integration tests for buy/sell workflows

## Phase 5: Portfolio Management
- [x] 5.1 Create `PortfolioService` to aggregate account data
- [x] 5.2 Implement cash balance retrieval
- [x] 5.3 Implement stock holdings list with average cost
- [x] 5.4 Implement crypto holdings list with average cost
- [x] 5.5 Calculate unrealized returns for each holding (current_value - cost_basis)
- [x] 5.6 Calculate percentage return for each holding
- [x] 5.7 Calculate total portfolio value (cash + holdings at current prices)
- [x] 5.8 Calculate total portfolio return
- [x] 5.9 Implement transaction history retrieval
- [x] 5.10 Write unit tests for portfolio calculations

## Phase 6: API Endpoints
- [x] 6.1 Implement `GET /api/portfolio` endpoint
- [x] 6.2 Implement `GET /api/portfolio/holdings` endpoint
- [x] 6.3 Implement `GET /api/portfolio/transactions` endpoint
- [x] 6.4 Implement `POST /api/trading/quote` endpoint
- [x] 6.5 Implement `POST /api/trading/buy` endpoint (returns preview)
- [x] 6.6 Implement `POST /api/trading/buy/confirm` endpoint
- [x] 6.7 Implement `POST /api/trading/sell` endpoint (returns preview)
- [x] 6.8 Implement `POST /api/trading/sell/confirm` endpoint
- [x] 6.9 Add request/response validation with Pydantic schemas
- [x] 6.10 Add proper HTTP error responses (400, 404, 422, 500)
- [x] 6.11 Write integration tests for all endpoints
- [x] 6.12 Add API documentation (auto-generated FastAPI docs)

## Phase 7: CLI / Interactive Interface
- [ ] 7.1 Add `typer` or `click` CLI framework
- [ ] 7.2 Implement `portfolio` command (show full portfolio)
- [ ] 7.3 Implement `buy` command with interactive prompts
- [ ] 7.4 Implement `sell` command with interactive prompts
- [ ] 7.5 Implement `quote` command (quick price lookup)
- [ ] 7.6 Implement `history` command (transaction history)
- [ ] 7.7 Add colored output for better UX (`rich` library)
- [ ] 7.8 Add confirmation prompts before executing trades
- [ ] 7.9 Handle invalid inputs gracefully
- [ ] 7.10 Write tests for CLI commands

## Phase 8: Testing & Quality Assurance
- [ ] 8.1 Set up `pytest` with fixtures
- [ ] 8.2 Set up test database (in-memory SQLite)
- [ ] 8.3 Write unit tests for all services (market, trading, portfolio)
- [ ] 8.4 Write integration tests for API endpoints
- [ ] 8.5 Set up code coverage reporting (`pytest-cov`)
- [ ] 8.6 Set up linting (`ruff` or `flake8` + `black`)
- [ ] 8.7 Set up type checking (`mypy`)
- [ ] 8.8 Add pre-commit hooks for linting and formatting
- [ ] 8.9 Write test for currency conversion logic
- [ ] 8.10 Write test for cost basis calculation edge cases

## Phase 9: Documentation & Polish
- [ ] 9.1 Complete `README.md` with full setup and usage instructions
- [ ] 9.2 Add API usage examples (curl commands)
- [ ] 9.3 Add CLI usage examples
- [ ] 9.4 Document supported exchanges and cryptocurrencies
- [ ] 9.5 Add architecture diagram to documentation
- [ ] 9.6 Add configuration reference (all env variables)
- [ ] 9.7 Add troubleshooting guide
- [ ] 9.8 Final code review and cleanup
- [ ] 9.9 Verify all TODO items are complete
- [ ] 9.10 Tag v1.0.0 release

---

## Tech Stack
- **Framework**: FastAPI + Uvicorn
- **Database**: SQLite + SQLAlchemy + Alembic
- **Validation**: Pydantic v2
- **Market Data**: Yahoo Finance (stocks), CoinGecko (crypto)
- **CLI**: Typer
- **Testing**: pytest + pytest-cov + httpx (for async tests)
- **Linting**: Ruff + Black
- **Type Checking**: mypy

## Notes
- All monetary values stored in USD (Decimal type)
- Currency conversion done at transaction time
- Cost basis uses average cost method
- Single account model (no multi-user auth in v1)
