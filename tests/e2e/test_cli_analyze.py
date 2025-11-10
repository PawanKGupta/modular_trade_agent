from src.presentation.cli.application import Application


class FakeBulkAnalyzeUseCase:
    def execute(self, request):
        from datetime import datetime
        from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse
        r = AnalysisResponse(
            ticker='RELIANCE.NS', status='success', timestamp=datetime.now(),
            verdict='buy', combined_score=40.0, priority_score=50.0
        )
        return BulkAnalysisResponse(
            results=[r], total_analyzed=1, successful=1, failed=0, buyable_count=1, timestamp=datetime.now(), execution_time_seconds=0.1
        )


class FakeSendAlertsUseCase:
    def execute(self, response, min_combined_score=0.0, use_final_verdict=False):
        return True


class FakeScraper:
    def get_stocks_with_suffix(self, suffix):
        return ['RELIANCE' + suffix]


class FakeFormatter:
    pass


def test_cli_analyze_with_explicit_ticker(monkeypatch):
    import src.presentation.cli.application as app_mod

    class FakeDI:
        def __init__(self):
            self.bulk_analyze_use_case = FakeBulkAnalyzeUseCase()
            self.send_alerts_use_case = FakeSendAlertsUseCase()
            self.chartink_scraper = FakeScraper()
            self.telegram_formatter = FakeFormatter()

    monkeypatch.setattr(app_mod, 'DIContainer', lambda: FakeDI())

    app = Application()
    code = app.run(['analyze', '--no-csv', '--no-mtf', '--no-alerts', 'RELIANCE'])
    assert code == 0


def test_cli_analyze_uses_scraper_when_no_ticker(monkeypatch):
    import src.presentation.cli.application as app_mod

    class FakeDI:
        def __init__(self):
            self.bulk_analyze_use_case = FakeBulkAnalyzeUseCase()
            self.send_alerts_use_case = FakeSendAlertsUseCase()
            self.chartink_scraper = FakeScraper()
            self.telegram_formatter = FakeFormatter()

    monkeypatch.setattr(app_mod, 'DIContainer', lambda: FakeDI())

    app = Application()
    code = app.run(['analyze', '--no-csv', '--no-mtf', '--no-alerts'])
    assert code == 0
