import types
import builtins
from datetime import datetime

import pytest

from src.infrastructure.persistence.csv_repository import CSVRepository


def test_csv_repository_save_and_bulk_and_master(monkeypatch):
    called = {
        'single': None,
        'bulk': None,
        'master': None,
    }

    class FakeExporter:
        def export_single_analysis(self, ticker, analysis_data):
            called['single'] = (ticker, analysis_data)

        def export_bulk_analysis(self, results, timestamp=None):
            called['bulk'] = (results, timestamp)
            return "path/to/file.csv"

        def append_to_master(self, analysis_data):
            called['master'] = analysis_data

    # Patch CSVExporter used inside CSVRepository
    import src.infrastructure.persistence.csv_repository as mod
    monkeypatch.setattr(mod, 'CSVExporter', lambda: FakeExporter())

    repo = CSVRepository()

    ok = repo.save_analysis('AAA.NS', {'a': 1})
    assert ok and called['single'][0] == 'AAA.NS'

    path = repo.save_bulk_analysis([{'a': 1}], timestamp=datetime(2025,1,1))
    assert path == "path/to/file.csv" and called['bulk'][0][0]['a'] == 1

    ok2 = repo.append_to_master({'b': 2})
    assert ok2 and called['master']['b'] == 2


def test_csv_repository_failure_paths(monkeypatch):
    class FailingExporter:
        def export_single_analysis(self, *args, **kwargs):
            raise RuntimeError('fail single')
        def export_bulk_analysis(self, *args, **kwargs):
            raise RuntimeError('fail bulk')
        def append_to_master(self, *args, **kwargs):
            raise RuntimeError('fail master')

    import src.infrastructure.persistence.csv_repository as mod
    monkeypatch.setattr(mod, 'CSVExporter', lambda: FailingExporter())

    repo = CSVRepository()
    assert repo.save_analysis('AAA.NS', {}) is False
    assert repo.save_bulk_analysis([{}]) is None
    assert repo.append_to_master({}) is False
