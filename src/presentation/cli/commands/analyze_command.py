"""
Analyze Command

CLI command for running stock analysis.
"""

import argparse
from typing import List

from ....application.use_cases.bulk_analyze import BulkAnalyzeUseCase
from ....application.use_cases.send_alerts import SendAlertsUseCase
from ....application.dto.analysis_request import BulkAnalysisRequest
from ....infrastructure.web_scraping.chartink_scraper import ChartInkScraper
from ...formatters.telegram_formatter import TelegramFormatter
from utils.logger import logger


class AnalyzeCommand:
    """
    Command for analyzing stocks
    
    Handles CLI arguments and orchestrates the analysis workflow.
    """
    
    def __init__(
        self,
        bulk_analyze: BulkAnalyzeUseCase,
        send_alerts: SendAlertsUseCase,
        scraper: ChartInkScraper,
        formatter: TelegramFormatter
    ):
        """
        Initialize command
        
        Args:
            bulk_analyze: Bulk analysis use case
            send_alerts: Alert sending use case
            scraper: Stock list scraper
            formatter: Message formatter
        """
        self.bulk_analyze = bulk_analyze
        self.send_alerts = send_alerts
        self.scraper = scraper
        self.formatter = formatter
    
    def execute(self, args: argparse.Namespace) -> int:
        """
        Execute analyze command
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code (0 = success)
        """
        try:
            # Get stock list
            tickers = self._get_tickers(args)
            
            if not tickers:
                logger.error("No stocks to analyze")
                return 1
            
            # Create request
            request = BulkAnalysisRequest(
                tickers=tickers,
                enable_multi_timeframe=not args.no_mtf,
                enable_backtest=args.backtest,
                export_to_csv=not args.no_csv,
                dip_mode=getattr(args, 'dip_mode', False),
                min_combined_score=getattr(args, 'min_score', 25.0)
            )
            
            # Execute analysis
            logger.info(f"Analyzing {len(tickers)} stocks...")
            response = self.bulk_analyze.execute(request)
            
            # Log results
            logger.info(
                f"Analysis complete: {response.successful}/{response.total_analyzed} successful, "
                f"{response.buyable_count} buyable ({response.execution_time_seconds:.2f}s)"
            )
            
            # Send alerts if enabled and has candidates
            if not getattr(args, 'no_alerts', False) and response.buyable_count > 0:
                # Apply min score filtering and use final_verdict when backtest is enabled
                min_score = getattr(args, 'min_score', 25.0) if args.backtest else 0.0
                success = self.send_alerts.execute(
                    response, 
                    min_combined_score=min_score,
                    use_final_verdict=args.backtest
                )
                if success:
                    logger.info(f"Sent alerts for {response.buyable_count} candidates")
                else:
                    logger.warning("Failed to send alerts")
            
            # Execute trades if requested
            if getattr(args, 'execute_trades', False):
                try:
                    from src.application.use_cases.execute_trades import ExecuteTradesUseCase
                    from src.infrastructure.persistence.trade_history_repository import TradeHistoryRepository
                    from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.mock_broker_adapter import MockBrokerAdapter
                    
                    # Choose broker
                    if getattr(args, 'use_live_broker', False):
                        try:
                            from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.kotak_neo_adapter import KotakNeoAdapter
                            broker = KotakNeoAdapter()
                        except Exception as e:
                            logger.error(f"Failed to initialize live broker: {e}")
                            return 1
                    else:
                        broker = MockBrokerAdapter()
                    history = TradeHistoryRepository(getattr(args, 'trade_csv', 'trade_history.csv'))
                    default_qty = int(getattr(args, 'qty', 1))
                    exec_uc = ExecuteTradesUseCase(broker_gateway=broker, trade_history_repo=history, default_quantity=default_qty)
                    min_score = getattr(args, 'min_score', 25.0) if args.backtest else 0.0
                    sell_pct = int(getattr(args, 'sell_pct', 100))
                    exec_summary = exec_uc.execute(
                        response,
                        min_combined_score=min_score,
                        place_sells_for_non_buyable=not getattr(args, 'no_sells', False),
                        use_final_verdict=args.backtest,
                        sell_percentage=sell_pct,
                    )
                    s = exec_summary.get_summary()
                    logger.info(f"Trades executed: placed={s['placed_count']} skipped={s['skipped_count']} failed={s['failed_count']}")
                except Exception as e:
                    logger.error(f"Trade execution failed: {e}")
                    return 1
            
            return 0
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return 1
    
    def _get_tickers(self, args: argparse.Namespace) -> List[str]:
        """Get list of tickers to analyze"""
        # Check if specific tickers provided
        if hasattr(args, 'tickers') and args.tickers:
            tickers = args.tickers
            # Add .NS suffix if not present
            return [t if t.endswith('.NS') else f"{t}.NS" for t in tickers]
        
        # Otherwise scrape from ChartInk
        logger.info("Scraping stocks from ChartInk...")
        return self.scraper.get_stocks_with_suffix(".NS")
    
    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        """Add command-specific arguments to parser"""
        parser.add_argument(
            'tickers',
            nargs='*',
            help='Specific tickers to analyze (optional, otherwise scrapes from ChartInk)'
        )
        parser.add_argument(
            '--no-csv',
            action='store_true',
            help='Disable CSV export'
        )
        parser.add_argument(
            '--no-mtf',
            action='store_true',
            help='Disable multi-timeframe analysis'
        )
        parser.add_argument(
            '--backtest',
            action='store_true',
            help='Enable backtest scoring (slower but more accurate)'
        )
        parser.add_argument(
            '--dip-mode',
            action='store_true',
            help='Enable dip-buying mode with permissive thresholds'
        )
        parser.add_argument(
            '--no-alerts',
            action='store_true',
            help='Disable sending alerts'
        )
        parser.add_argument(
            '--min-score',
            type=float,
            default=25.0,
            help='Minimum combined score for filtering (default: 25.0)'
        )
        # Trade execution options
        parser.add_argument(
            '--execute-trades',
            action='store_true',
            help='Execute market orders for buy candidates (uses mock broker by default)'
        )
        parser.add_argument(
            '--qty',
            type=int,
            default=1,
            help='Default quantity per BUY order (default: 1)'
        )
        parser.add_argument(
            '--no-sells',
            action='store_true',
            help='Do not place SELL orders for existing non-recommended holdings'
        )
        parser.add_argument(
            '--trade-csv',
            type=str,
            default='trade_history.csv',
            help='Path to trade history CSV file'
        )
        parser.add_argument(
            '--sell-pct',
            type=int,
            default=100,
            help='Percentage of existing holdings to sell when not recommended (default: 100)'
        )
        parser.add_argument(
            '--use-live-broker',
            action='store_true',
            help='Use the live Kotak broker adapter instead of mock (requires valid credentials)'
        )
