from datetime import datetime, timedelta
import pandas as pd

from backtest.position_manager import PositionManager
from backtest.backtest_config import BacktestConfig
from backtest.performance_analyzer import PerformanceAnalyzer


class FakeEngine:
    def __init__(self):
        self.symbol = 'TEST.NS'
        self.results = {
            'symbol': 'TEST.NS',
            'period': '2024-01-01 to 2024-02-01',
            'total_trades': 2,
            'total_invested': 200000.0,
            'total_pnl': 15000.0,
            'total_return_pct': 7.5,
            'win_rate': 50.0,
            'avg_win': 10000.0,
            'avg_loss': -5000.0,
            'strategy_vs_buy_hold': 2.0,
        }
        self._trades_df = None

    def get_trades_dataframe(self):
        if self._trades_df is None:
            now = datetime.now()
            data = [
                {
                    'symbol': 'TEST.NS', 'position_id': 1,
                    'entry_date': now - timedelta(days=20),
                    'entry_price': 100.0, 'quantity': 500, 'capital': 50000.0,
                    'entry_reason': 'Entry 1', 'exit_date': now - timedelta(days=10),
                    'exit_price': 110.0, 'exit_reason': 'Target', 'is_open': False,
                    'pnl': 5000.0, 'pnl_pct': 10.0,
                },
                {
                    'symbol': 'TEST.NS', 'position_id': 2,
                    'entry_date': now - timedelta(days=15),
                    'entry_price': 200.0, 'quantity': 750, 'capital': 150000.0,
                    'entry_reason': 'Entry 2', 'exit_date': now - timedelta(days=5),
                    'exit_price': 195.0, 'exit_reason': 'Stop', 'is_open': False,
                    'pnl': -3750.0, 'pnl_pct': -2.5,
                },
            ]
            self._trades_df = pd.DataFrame(data)
        return self._trades_df


def test_position_manager_basic_operations():
    cfg = BacktestConfig()
    pm = PositionManager('ABC.NS', cfg)

    pos = pm.add_position(entry_date=datetime.now(), entry_price=100.0, entry_reason='test')
    assert pos is not None
    assert pm.get_total_quantity() > 0
    assert pm.get_average_entry_price() > 0

    pm.close_all_positions(exit_date=datetime.now(), exit_price=110.0, exit_reason='end')
    df = pm.get_trades_dataframe()
    assert not df.empty
    assert (df['pnl'] != 0).any()


def test_performance_analyzer_end_to_end():
    eng = FakeEngine()
    analyzer = PerformanceAnalyzer(eng)
    metrics = analyzer.analyze_performance()
    assert metrics['total_trades'] == 2
    assert 'sharpe_ratio' in metrics and 'max_drawdown_pct' in metrics

    report = analyzer.generate_report(save_to_file=False)
    assert 'BACKTEST PERFORMANCE REPORT' in report
