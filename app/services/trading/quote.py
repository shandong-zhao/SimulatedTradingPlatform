"""Quote generation service for trading."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Account, CryptoHolding, StockHolding
from app.schemas.trading import BuyQuote, SellQuote
from app.services.market_data.exchange import ExchangeRateService
from app.services.market_data.resolver import PriceResolver

logger = get_logger(__name__)


class QuoteService:
    """Service for generating buy and sell quotes."""

    def __init__(self) -> None:
        """Initialize the quote service with required dependencies."""
        self._price_resolver = PriceResolver()
        self._exchange_service = ExchangeRateService()

    async def generate_buy_quote(
        self,
        symbol: str,
        exchange: str,
        currency: str,
        usd_amount: Decimal,
        asset_type: str,
    ) -> BuyQuote:
        """Generate a buy quote for an asset.

        Args:
            symbol: The asset symbol.
            exchange: The exchange code.
            currency: The currency code.
            usd_amount: The amount in USD to invest.
            asset_type: The asset type (stock or crypto).

        Returns:
            A BuyQuote with calculated quantity and pricing.
        """
        logger.info(
            "Generating buy quote",
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            usd_amount=str(usd_amount),
            asset_type=asset_type,
        )

        usd_price_per_unit = await self._price_resolver.get_price(symbol)

        if currency.upper() == "USD":
            exchange_rate = Decimal("1")
            price_per_unit = usd_price_per_unit
        else:
            exchange_rate = await self._exchange_service.get_rate("USD", currency)
            price_per_unit = usd_price_per_unit * exchange_rate

        quantity = usd_amount / usd_price_per_unit
        total_usd_value = quantity * usd_price_per_unit
        estimated_fees = Decimal("0")

        return BuyQuote(
            symbol=symbol.upper(),
            exchange=exchange.upper(),
            currency=currency.upper(),
            asset_type=asset_type.lower(),
            price_per_unit=price_per_unit,
            usd_price_per_unit=usd_price_per_unit,
            exchange_rate=exchange_rate,
            quantity=quantity,
            total_usd_value=total_usd_value,
            estimated_fees=estimated_fees,
            preview=True,
        )

    async def generate_sell_quote(
        self,
        account_id: str,
        symbol: str,
        exchange: str,
        currency: str,
        quantity: Decimal,
        asset_type: str,
        db_session: AsyncSession,
    ) -> SellQuote:
        """Generate a sell quote for an asset.

        Args:
            account_id: The account ID.
            symbol: The asset symbol.
            exchange: The exchange code.
            currency: The currency code.
            quantity: The quantity to sell.
            asset_type: The asset type (stock or crypto).
            db_session: The database session.

        Returns:
            A SellQuote with calculated pricing and holding info.

        Raises:
            ValueError: If the account does not hold enough of the asset.
        """
        logger.info(
            "Generating sell quote",
            account_id=account_id,
            symbol=symbol,
            exchange=exchange,
            currency=currency,
            quantity=str(quantity),
            asset_type=asset_type,
        )

        # Validate account and holding
        account_result = await db_session.execute(select(Account).where(Account.id == account_id))
        account = account_result.scalar_one_or_none()
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        holding = None
        if asset_type.lower() == "stock":
            holding_result = await db_session.execute(
                select(StockHolding).where(
                    StockHolding.account_id == account_id,
                    StockHolding.symbol == symbol.upper(),
                    StockHolding.exchange == exchange.upper(),
                )
            )
            holding = holding_result.scalar_one_or_none()
        elif asset_type.lower() == "crypto":
            holding_result = await db_session.execute(
                select(CryptoHolding).where(
                    CryptoHolding.account_id == account_id,
                    CryptoHolding.symbol == symbol.upper(),
                )
            )
            holding = holding_result.scalar_one_or_none()

        if holding is None or holding.quantity < quantity:
            available = holding.quantity if holding else Decimal("0")
            raise ValueError(
                f"Insufficient {asset_type} holdings: requested {quantity}, available {available}"
            )

        usd_price_per_unit = await self._price_resolver.get_price(symbol)

        if currency.upper() == "USD":
            exchange_rate = Decimal("1")
            price_per_unit = usd_price_per_unit
        else:
            exchange_rate = await self._exchange_service.get_rate("USD", currency)
            price_per_unit = usd_price_per_unit * exchange_rate

        total_usd_value = quantity * usd_price_per_unit
        estimated_fees = Decimal("0")
        unrealized_pnl = (usd_price_per_unit - holding.avg_cost_basis) * quantity

        return SellQuote(
            symbol=symbol.upper(),
            exchange=exchange.upper(),
            currency=currency.upper(),
            asset_type=asset_type.lower(),
            price_per_unit=price_per_unit,
            usd_price_per_unit=usd_price_per_unit,
            exchange_rate=exchange_rate,
            quantity=quantity,
            total_usd_value=total_usd_value,
            estimated_fees=estimated_fees,
            holding_quantity=holding.quantity,
            avg_cost_basis=holding.avg_cost_basis,
            unrealized_pnl=unrealized_pnl,
            preview=True,
        )
