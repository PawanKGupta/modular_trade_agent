import types
import builtins
import argparse

from src.presentation.cli.commands.backtest_command import BacktestCommand


class Args:
    def __init__(self, tickers=None, start_date='2020-01-01', end_date='2020-12-31'):
        self.tickers = tickers or []
        self.start_date = start_date
        self.end_date = end_date


def test_backtest_command_with_explicit_tickers(monkeypatch):
    # Patch integrated_backtest module used inside command
    fake_module = types.SimpleNamespace(run_integrated_backtest=lambda stock_name, date_range, capital_per_position: {
        'ticker': stock_name,
        'executed_trades': 5,
    })
    import sys
    sys.modules['integrated_backtest'] = fake_module

    class FakeScraper:
        def get_stocks_with_suffix(self, suffix):
            return ['AAA.NS', 'BBB.NS']

    cmd = BacktestCommand(scraper=FakeScraper())

    code = cmd.execute(Args(tickers=['X','Y']))
    assert code == 0


def test_backtest_command_uses_scraper_when_no_tickers(monkeypatch):
    fake_module = types.SimpleNamespace(run_integrated_backtest=lambda stock_name, date_range, capital_per_position: {
        'ticker': stock_name,
        'executed_trades': 1,
    })
    import sys
    sys.modules['integrated_backtest'] = fake_module

    class FakeScraper:
        def get_stocks_with_suffix(self, suffix):
            return ['CCC.NS']

    cmd = BacktestCommand(scraper=FakeScraper())
    code = cmd.execute(Args())
    assert code == 0
