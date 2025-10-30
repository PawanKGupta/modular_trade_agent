from datetime import datetime
import os

import pytest

from src.application.use_cases.execute_trades import ExecuteTradesUseCase
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse
from src.infrastructure.persistence.trade_history_repository import TradeHistoryRepository
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.mock_broker_adapter import MockBrokerAdapter
from modules.kotak_neo_auto_trader.domain.value_objects.money import Money


def make_resp(ticker, verdict='buy', combined=50.0, last_close=100.0):
    return AnalysisResponse(
        ticker=ticker,
        status='success',
        timestamp=datetime.now(),
        verdict=verdict,
        last_close=last_close,
        combined_score=combined,
    )


def test_execute_trades_buy_and_sell_and_record_csv(tmp_path):
    broker = MockBrokerAdapter()
    # Seed a holding that should be sold because not in buy list
    broker.add_holding(symbol='SELLME.NS', quantity=3, avg_price=90.0, current_price=95.0)

    # Build recommendations: one buyable, one not buyable (watch)
    r_buy = make_resp('BUYME.NS', verdict='buy', combined=60.0, last_close=123.0)
    r_watch = make_resp('SELLME.NS', verdict='watch', combined=10.0, last_close=95.0)

    bulk = BulkAnalysisResponse(
        results=[r_buy, r_watch],
        total_analyzed=2,
        successful=2,
        failed=0,
        buyable_count=1,
        timestamp=datetime.now(),
        execution_time_seconds=0.1,
    )

    csv_path = tmp_path / 'trades.csv'
    history = TradeHistoryRepository(str(csv_path))

    uc = ExecuteTradesUseCase(broker_gateway=broker, trade_history_repo=history, default_quantity=2)
    summary = uc.execute(bulk, min_combined_score=0.0, place_sells_for_non_buyable=True)

    assert summary.success
    # Expect at least one BUY for BUYME and one SELL for SELLME holding
    sides = [o['side'] for o in summary.orders_placed]
    assert 'BUY' in sides and 'SELL' in sides

    # CSV should contain the recorded trades
    rows = history.read_all()
    assert len(rows) >= 2
    tickers = {row['ticker'] for row in rows}
    assert {'BUYME.NS', 'SELLME.NS'} <= tickers