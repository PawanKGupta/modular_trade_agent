import builtins
import argparse
from datetime import datetime

import src.presentation.cli.commands.analyze_command as mod
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse


class FakeBulkAnalyze:
    def execute(self, req):
        r_buy = AnalysisResponse(
            ticker='AAA.NS', status='success', timestamp=datetime.now(), verdict='buy', combined_score=50.0, last_close=100.0
        )
        r_watch = AnalysisResponse(
            ticker='BBB.NS', status='success', timestamp=datetime.now(), verdict='watch', combined_score=10.0, last_close=90.0
        )
        return BulkAnalysisResponse(
            results=[r_buy, r_watch], total_analyzed=2, successful=2, failed=0, buyable_count=1, timestamp=datetime.now(), execution_time_seconds=0.1
        )


class FakeSendAlerts:
    def execute(self, resp, min_combined_score=0.0, use_final_verdict=False):
        return True


class FakeScraper:
    def get_stocks_with_suffix(self, suffix):
        return ['AAA' + suffix, 'BBB' + suffix]


class FakeFormatter:
    pass


class FakeExecUC:
    def __init__(self, *a, **k):
        self.called = False
    def execute(self, response, min_combined_score=0.0, place_sells_for_non_buyable=True, use_final_verdict=False):
        self.called = True
        # Simulate placing exactly one order
        class S:
            def get_summary(self_inner):
                return {'placed_count': 1, 'skipped_count': 0, 'failed_count': 0}
        return S()


def test_analyze_command_executes_trades(monkeypatch, tmp_path):
    # Silence logging/prints
    monkeypatch.setattr(builtins, 'print', lambda *a, **k: None)

    # Use real ExecuteTradesUseCase with mock broker (no external side-effects)

    cmd = mod.AnalyzeCommand(
        bulk_analyze=FakeBulkAnalyze(),
        send_alerts=FakeSendAlerts(),
        scraper=FakeScraper(),
        formatter=FakeFormatter(),
    )

    args = argparse.Namespace(
        tickers=['AAA','BBB'], no_mtf=True, backtest=False, no_csv=True, dip_mode=False,
        no_alerts=True, min_score=0.0, execute_trades=True, qty=2, no_sells=False, trade_csv=str(tmp_path/'trades.csv')
    )

    code = cmd.execute(args)
    assert code == 0
    # Trade CSV should be created
    import os
    assert os.path.exists(args.trade_csv)
