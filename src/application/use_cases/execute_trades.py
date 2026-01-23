"""
Execute Trades Use Case

Places buy/sell orders based on analysis recommendations and records trade history.
"""

from dataclasses import dataclass, field
from datetime import datetime
from math import floor
from typing import Any

# Use Kotak module DTOs and enums for orders
from modules.kotak_neo_auto_trader.application.dto.order_request import OrderRequest
from modules.kotak_neo_auto_trader.application.use_cases.place_order import PlaceOrderUseCase
from modules.kotak_neo_auto_trader.domain.interfaces.broker_gateway import IBrokerGateway
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import (
    OrderType,
    OrderVariety,
    ProductType,
    TransactionType,
)
from modules.kotak_neo_auto_trader.order_tracker import (
    add_pending_order,
    configure_order_tracker,
)
from src.application.services.conflict_detection_service import ConflictDetectionService
from src.infrastructure.persistence.individual_service_status_repository import (
    IndividualServiceStatusRepository,
)
from src.infrastructure.persistence.user_trading_config_repository import (
    UserTradingConfigRepository,
)
from utils.logger import logger

from ..dto.analysis_response import BulkAnalysisResponse


@dataclass
class TradeExecutionSummary:
    success: bool
    orders_placed: list[dict[str, Any]] = field(default_factory=list)
    orders_skipped: list[dict[str, Any]] = field(default_factory=list)
    orders_failed: list[dict[str, Any]] = field(default_factory=list)

    def get_summary(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "placed_count": len(self.orders_placed),
            "skipped_count": len(self.orders_skipped),
            "failed_count": len(self.orders_failed),
            "total_processed": len(self.orders_placed)
            + len(self.orders_skipped)
            + len(self.orders_failed),
        }


class ExecuteTradesUseCase:
    """
    Execute trades based on analysis recommendations.

    - Places market BUY orders for 'buy'/'strong_buy' candidates
    - Places market SELL orders for holdings that are no longer recommended (optional)
    - Records trades to a history repository if provided
    """

    def __init__(
        self,
        broker_gateway: IBrokerGateway,
        trade_history_repo=None,
        default_quantity: int = 1,
        user_id: int | None = None,
        db_session=None,
    ):
        self.broker = broker_gateway
        self.trade_history = trade_history_repo
        self.default_quantity = max(1, int(default_quantity))
        self.user_id = user_id
        self.db_session = db_session
        # Use the module's PlaceOrderUseCase to convert DTO -> domain Order
        self.place_order_uc = PlaceOrderUseCase(broker_gateway=self.broker)

        # Configure order tracker if user_id and db_session are available
        if self.user_id and self.db_session:
            try:
                configure_order_tracker(
                    db_session=self.db_session,
                    user_id=self.user_id,
                    use_db=True,
                    db_only_mode=True,
                )
            except Exception as e:
                logger.warning(f"Failed to configure order tracker: {e}")

    def _get_execution_capital(self) -> float:
        """
        Get execution capital from user config or use default.

        Returns:
            Execution capital per trade (default: 1.0 if no config available, ensures minimum 1 qty)
        """
        if self.user_id and self.db_session:
            try:
                config_repo = UserTradingConfigRepository(self.db_session)
                config = config_repo.get_or_create_default(self.user_id)
                if config and config.user_capital:
                    return float(config.user_capital)
            except Exception as e:
                logger.warning(f"Failed to get user capital from config: {e}, using default")

        # Fallback to 1.0 if no user config available
        # This ensures minimum 1 qty in worst case (qty = max(1, floor(1/price)) = 1)
        return 1.0

    def _is_order_monitoring_active(self) -> bool:
        """
        Check if order monitoring is active (unified service or sell_monitor individual service).

        Returns:
            True if unified service OR sell_monitor service is running
        """
        if not self.user_id or not self.db_session:
            return False

        try:
            # Check unified service
            conflict_service = ConflictDetectionService(self.db_session)
            if conflict_service.is_unified_service_running(self.user_id):
                return True

            # Check sell_monitor individual service
            status_repo = IndividualServiceStatusRepository(self.db_session)
            sell_monitor_status = status_repo.get_by_user_and_task(self.user_id, "sell_monitor")
            if sell_monitor_status and sell_monitor_status.is_running:
                return True
        except Exception as e:
            logger.debug(f"Error checking order monitoring status: {e}")

        return False

    def execute(  # noqa: PLR0912, PLR0915
        self,
        bulk_response: BulkAnalysisResponse,
        min_combined_score: float = 0.0,
        place_sells_for_non_buyable: bool = True,
        use_final_verdict: bool = False,
        sell_percentage: int = 100,
    ) -> TradeExecutionSummary:
        summary = TradeExecutionSummary(success=True)

        try:
            if not self.broker.is_connected():
                if not self.broker.connect():
                    logger.error("Broker connection failed")
                    summary.success = False
                    return summary

            # Get execution capital from user config (fallback to 1.0)
            default_execution_capital = self._get_execution_capital()
            logger.info(
                f"Using execution capital: Rs {default_execution_capital:,.0f} "
                f"per trade (from user config)"
            )

            # Place BUY orders for candidates
            buy_candidates = bulk_response.get_buy_candidates(
                min_combined_score=min_combined_score,
                use_final_verdict=use_final_verdict,
            )

            for stock in buy_candidates:
                try:
                    # Try to get execution_capital from stock recommendation first
                    stock_execution_capital = getattr(stock, "execution_capital", None)

                    # Use stock's execution_capital if available, otherwise use user config
                    if stock_execution_capital and stock_execution_capital > 0:
                        capital_to_use = stock_execution_capital
                    else:
                        capital_to_use = default_execution_capital

                    price = stock.last_close
                    if price <= 0:
                        logger.warning(f"Invalid price for {stock.ticker}: {price}")
                        summary.orders_failed.append(
                            {"ticker": stock.ticker, "error": f"Invalid price: {price}"}
                        )
                        continue

                    # Calculate quantity based on execution capital and price
                    # max(1, ...) ensures minimum 1 qty even if capital is very low
                    qty = max(1, floor(capital_to_use / price))

                    logger.debug(
                        f"Calculated quantity for {stock.ticker}: "
                        f"{qty} shares (capital: Rs {capital_to_use:,.0f}, price: Rs {price:.2f})"
                    )
                    req = OrderRequest.market_buy(
                        symbol=stock.ticker,
                        quantity=qty,
                        variety=OrderVariety.REGULAR,
                        product_type=ProductType.CNC,
                    )
                    # Delegate to place order use case
                    resp = self.place_order_uc.execute(req)
                    if not resp.success:
                        error_msg = "; ".join(resp.errors) if resp.errors else resp.message
                        raise RuntimeError(f"Order failed: {error_msg}")
                    order_id = resp.order_id or ""
                    record = {
                        "timestamp": datetime.now().isoformat(),
                        "ticker": stock.ticker,
                        "side": "BUY",
                        "quantity": qty,
                        "price": stock.last_close,
                        "order_id": order_id,
                        "verdict": stock.final_verdict or stock.verdict,
                        "combined_score": stock.combined_score,
                    }
                    summary.orders_placed.append(record)
                    self._record_trade(record)

                    # Track order in database (Phase 1: Order tracking)
                    if order_id and self.user_id and self.db_session:
                        try:
                            add_pending_order(
                                order_id=order_id,
                                symbol=stock.ticker,
                                ticker=stock.ticker,
                                qty=qty,
                                order_type="MARKET",
                                variety="REGULAR",
                                price=0.0,
                                entry_type="initial",
                                order_metadata={
                                    "verdict": stock.final_verdict or stock.verdict,
                                    "combined_score": stock.combined_score,
                                    "execution_capital": capital_to_use,
                                },
                            )
                            logger.debug(f"Order {order_id} tracked in database")

                            # Check if order monitoring is active
                            if self._is_order_monitoring_active():
                                # Monitoring is active - periodic sync will handle status updates
                                logger.debug(
                                    f"Order {order_id} tracked. "
                                    f"Status will sync via active monitoring service."
                                )
                            else:
                                # No monitoring active - suggest manual sync
                                msg = (
                                    f"Order {order_id} placed but monitoring service "
                                    f"is not running. Use POST /api/v1/user/orders/sync "
                                    f"to update status."
                                )
                                logger.info(msg)
                        except Exception as e:
                            logger.warning(f"Failed to track order {order_id}: {e}")
                            # Don't fail order placement if tracking fails
                except Exception as e:
                    logger.error(f"Failed to buy {stock.ticker}: {e}")
                    summary.orders_failed.append({"ticker": stock.ticker, "error": str(e)})

            # Optional: Place SELL orders for existing holdings that are not buyable
            if place_sells_for_non_buyable:
                try:
                    holdings = {h.symbol.upper(): h for h in self.broker.get_holdings()}
                except Exception:
                    holdings = {}

                non_buy_tickers = set(holdings.keys()) - {s.ticker.upper() for s in buy_candidates}
                sell_pct = max(0, min(100, int(sell_percentage)))
                for ticker in non_buy_tickers:
                    holding = holdings.get(ticker)
                    if not holding or holding.quantity <= 0:
                        continue
                    try:
                        # Determine quantity to sell (partial or full)
                        qty_to_sell = (
                            int(max(1, round((holding.quantity * sell_pct) / 100)))
                            if sell_pct > 0
                            else 0
                        )
                        if qty_to_sell <= 0:
                            continue
                        # Create a SELL market order request (manually)
                        sell_req = OrderRequest(
                            symbol=ticker,
                            quantity=qty_to_sell,
                            order_type=OrderType.MARKET,
                            transaction_type=TransactionType.SELL,
                            variety=OrderVariety.REGULAR,
                            product_type=ProductType.CNC,
                        )
                        resp = self.place_order_uc.execute(sell_req)
                        if not resp.success:
                            error_msg = "; ".join(resp.errors) if resp.errors else resp.message
                            raise RuntimeError(f"Sell failed: {error_msg}")
                        order_id = resp.order_id or ""
                        record = {
                            "timestamp": datetime.now().isoformat(),
                            "ticker": ticker,
                            "side": "SELL",
                            "quantity": qty_to_sell,
                            "price": (
                                float(holding.current_price.amount)
                                if getattr(holding, "current_price", None)
                                else None
                            ),
                            "order_id": order_id,
                            "verdict": "exit",
                            "combined_score": None,
                        }
                        summary.orders_placed.append(record)
                        self._record_trade(record)

                        # Track sell order in database (Phase 1: Order tracking)
                        if order_id and self.user_id and self.db_session:
                            try:
                                add_pending_order(
                                    order_id=order_id,
                                    symbol=ticker,
                                    ticker=ticker,
                                    qty=qty_to_sell,
                                    order_type="MARKET",
                                    variety="REGULAR",
                                    price=0.0,
                                    entry_type="exit",
                                    order_metadata={
                                        "verdict": "exit",
                                        "sell_percentage": sell_pct,
                                    },
                                )
                                logger.debug(f"Sell order {order_id} tracked in database")
                            except Exception as e:
                                logger.warning(f"Failed to track sell order {order_id}: {e}")
                                # Don't fail order placement if tracking fails
                    except Exception as e:
                        logger.error(f"Failed to sell {ticker}: {e}")
                        summary.orders_failed.append({"ticker": ticker, "error": str(e)})

            return summary
        except Exception as e:
            logger.error(f"ExecuteTradesUseCase failed: {e}")
            summary.success = False
            return summary

    def _record_trade(self, record: dict[str, Any]):
        if self.trade_history:
            try:
                self.trade_history.record_trade(record)
            except Exception as e:
                logger.warning(f"Failed to record trade: {e}")
