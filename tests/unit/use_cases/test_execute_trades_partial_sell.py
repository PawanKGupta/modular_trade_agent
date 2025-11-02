from datetime import datetime

from src.application.use_cases.execute_trades import ExecuteTradesUseCase
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.mock_broker_adapter import MockBrokerAdapter
from modules.kotak_neo_auto_trader.domain.value_objects.money import Money


def make_resp(ticker, verdict='watch', combined=10.0, last_close=100.0):
    return AnalysisResponse(
        ticker=ticker,
        status='success',
        timestamp=datetime.now(),
        verdict=verdict,
        last_close=last_close,
        combined_score=combined,
    )


def test_partial_sell_percentage(monkeypatch):
    broker = MockBrokerAdapter()
    broker.add_holding(symbol='PART.NS', quantity=10, avg_price=90.0, current_price=95.0)

    # No buy candidates, so PART.NS should be sold partially
    bulk = BulkAnalysisResponse(
        results=[make_resp('PART.NS', verdict='watch', combined=10.0)],
        total_analyzed=1,
        successful=1,
        failed=0,
        buyable_count=0,
        timestamp=datetime.now(),
        execution_time_seconds=0.1,
    )

    uc = ExecuteTradesUseCase(broker_gateway=broker, trade_history_repo=None, default_quantity=1)
    summary = uc.execute(bulk, place_sells_for_non_buyable=True, sell_percentage=50)

    # Ensure a SELL order of approx half quantity (>=1)
    sells = [o for o in summary.orders_placed if o['side'] == 'SELL']
    assert sells, 'No SELL orders placed'
    # Since we can't directly read the order quantity from mock order here,
    # rely on recorded field in summary
    qty = sells[0]['quantity']
    assert qty == 5