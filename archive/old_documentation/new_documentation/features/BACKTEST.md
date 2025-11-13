# Backtesting — Details and Commands

What it does
- Validates strategy historically and produces analytics & exports

Quick Python API
```powershell
.\.venv\Scripts\python.exe - << 'PY'
from backtest import BacktestEngine, PerformanceAnalyzer
engine = BacktestEngine("RELIANCE.NS", "2022-01-01", "2023-12-31")
results = engine.run_backtest()
analyzer = PerformanceAnalyzer(engine)
print(analyzer.generate_report(save_to_file=False))
PY
```

Notes
- Results/exports are saved under standard backtest paths (see documents/backtest/README.md)
- Use API to compare multiple stocks or parameter sets
