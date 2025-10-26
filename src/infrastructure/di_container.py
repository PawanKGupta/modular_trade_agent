"""
Dependency Injection Container

Central container for creating and managing all application dependencies.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DIContainer:
    """
    Dependency Injection Container
    
    Provides lazy initialization of all application components with proper
    dependency wiring.
    """
    
    def __init__(self):
        """Initialize container"""
        self._instances = {}
    
    # ========== Infrastructure Layer ==========
    
    @property
    def data_service(self):
        """Stock data fetching service"""
        if 'data_service' not in self._instances:
            from .data_providers.yfinance_provider import YFinanceProvider
            self._instances['data_service'] = YFinanceProvider()
        return self._instances['data_service']
    
    @property
    def scoring_service(self):
        """Technical analysis scoring service"""
        if 'scoring_service' not in self._instances:
            from ..application.services.scoring_service import ScoringService
            self._instances['scoring_service'] = ScoringService()
        return self._instances['scoring_service']
    
    @property
    def telegram_client(self):
        """Telegram notification client"""
        if 'telegram_client' not in self._instances:
            from .notifications.telegram_notifier import TelegramNotifier
            self._instances['telegram_client'] = TelegramNotifier()
        return self._instances['telegram_client']
    
    @property
    def chartink_scraper(self):
        """ChartInk stock list scraper"""
        if 'chartink_scraper' not in self._instances:
            from .web_scraping.chartink_scraper import ChartInkScraper
            self._instances['chartink_scraper'] = ChartInkScraper()
        return self._instances['chartink_scraper']
    
    @property
    def csv_exporter(self):
        """CSV export service"""
        if 'csv_exporter' not in self._instances:
            from .persistence.csv_repository import CSVRepository
            self._instances['csv_exporter'] = CSVRepository()
        return self._instances['csv_exporter']
    
    # ========== Presentation Layer ==========
    
    @property
    def telegram_formatter(self):
        """Telegram message formatter"""
        if 'telegram_formatter' not in self._instances:
            from ..presentation.formatters.telegram_formatter import TelegramFormatter
            self._instances['telegram_formatter'] = TelegramFormatter()
        return self._instances['telegram_formatter']
    
    # ========== Application Layer (Use Cases) ==========
    
    @property
    def analyze_stock_use_case(self):
        """Single stock analysis use case"""
        if 'analyze_stock_use_case' not in self._instances:
            from ..application.use_cases.analyze_stock import AnalyzeStockUseCase
            self._instances['analyze_stock_use_case'] = AnalyzeStockUseCase(
                scoring_service=self.scoring_service
            )
        return self._instances['analyze_stock_use_case']
    
    @property
    def bulk_analyze_use_case(self):
        """Bulk stock analysis use case"""
        if 'bulk_analyze_use_case' not in self._instances:
            from ..application.use_cases.bulk_analyze import BulkAnalyzeUseCase
            self._instances['bulk_analyze_use_case'] = BulkAnalyzeUseCase(
                analyze_stock_use_case=self.analyze_stock_use_case,
                scoring_service=self.scoring_service
            )
        return self._instances['bulk_analyze_use_case']
    
    @property
    def send_alerts_use_case(self):
        """Alert sending use case"""
        if 'send_alerts_use_case' not in self._instances:
            from ..application.use_cases.send_alerts import SendAlertsUseCase
            self._instances['send_alerts_use_case'] = SendAlertsUseCase()
        return self._instances['send_alerts_use_case']
