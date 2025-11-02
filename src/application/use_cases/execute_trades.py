"""
Execute Trades Use Case

Places buy/sell orders based on analysis recommendations and records trade history.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..dto.analysis_response import BulkAnalysisResponse, AnalysisResponse
from utils.logger import logger

# Use Kotak module DTOs and enums for orders
from modules.kotak_neo_auto_trader.application.dto.order_request import OrderRequest
from modules.kotak_neo_auto_trader.application.use_cases.place_order import PlaceOrderUseCase
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import (
    OrderType, TransactionType, OrderVariety, ProductType
)
from modules.kotak_neo_auto_trader.domain.interfaces.broker_gateway import IBrokerGateway


@dataclass
class TradeExecutionSummary:
    success: bool
    orders_placed: List[Dict[str, Any]] = field(default_factory=list)
    orders_skipped: List[Dict[str, Any]] = field(default_factory=list)
    orders_failed: List[Dict[str, Any]] = field(default_factory=list)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "placed_count": len(self.orders_placed),
            "skipped_count": len(self.orders_skipped),
            "failed_count": len(self.orders_failed),
            "total_processed": len(self.orders_placed) + len(self.orders_skipped) + len(self.orders_failed),
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
    ):
        self.broker = broker_gateway
        self.trade_history = trade_history_repo
        self.default_quantity = max(1, int(default_quantity))
        # Use the module's PlaceOrderUseCase to convert DTO -> domain Order
        self.place_order_uc = PlaceOrderUseCase(broker_gateway=self.broker)

    def execute(
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

            # Place BUY orders for candidates
            buy_candidates = bulk_response.get_buy_candidates(
                min_combined_score=min_combined_score,
                use_final_verdict=use_final_verdict,
            )

            for stock in buy_candidates:
                try:
                    qty = self.default_quantity
                    req = OrderRequest.market_buy(
                        symbol=stock.ticker,
                        quantity=qty,
                        variety=OrderVariety.REGULAR,
                        product_type=ProductType.CNC,
                    )
                    # Delegate to place order use case
                    resp = self.place_order_uc.execute(req)
                    if not resp.success:
                        raise RuntimeError(
                            f"Order failed: {'; '.join(resp.errors) if resp.errors else resp.message}"
                        )
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
                        qty_to_sell = int(max(1, round((holding.quantity * sell_pct) / 100))) if sell_pct > 0 else 0
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
                            raise RuntimeError(
                                f"Sell failed: {'; '.join(resp.errors) if resp.errors else resp.message}"
                            )
                        order_id = resp.order_id or ""
                        record = {
                            "timestamp": datetime.now().isoformat(),
                            "ticker": ticker,
                            "side": "SELL",
                            "quantity": qty_to_sell,
                            "price": float(holding.current_price.amount) if getattr(holding, 'current_price', None) else None,
                            "order_id": order_id,
                            "verdict": "exit",
                            "combined_score": None,
                        }
                        summary.orders_placed.append(record)
                        self._record_trade(record)
                    except Exception as e:
                        logger.error(f"Failed to sell {ticker}: {e}")
                        summary.orders_failed.append({"ticker": ticker, "error": str(e)})

            return summary
        except Exception as e:
            logger.error(f"ExecuteTradesUseCase failed: {e}")
            summary.success = False
            return summary

    def _record_trade(self, record: Dict[str, Any]):
        if self.trade_history:
            try:
                self.trade_history.record_trade(record)
            except Exception as e:
                logger.warning(f"Failed to record trade: {e}")
