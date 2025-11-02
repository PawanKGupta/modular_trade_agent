"""
Analysis Service

Main orchestrator service that coordinates all analysis components.
This service replaces the monolithic analyze_ticker() function with a
clean, modular, testable architecture.
"""

import pandas as pd
from typing import Optional, Dict, Any

from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.signal_service import SignalService
from services.verdict_service import VerdictService
from core.csv_exporter import CSVExporter
from utils.logger import logger
from config.strategy_config import StrategyConfig


class AnalysisService:
    """
    Main analysis service that orchestrates stock analysis pipeline.
    
    This service coordinates:
    1. Data fetching
    2. Indicator calculation
    3. Signal detection
    4. Verdict determination
    5. Trading parameter calculation
    """
    
    def __init__(
        self,
        data_service: Optional[DataService] = None,
        indicator_service: Optional[IndicatorService] = None,
        signal_service: Optional[SignalService] = None,
        verdict_service: Optional[VerdictService] = None,
        config: Optional[StrategyConfig] = None
    ):
        """
        Initialize analysis service with dependencies
        
        Args:
            data_service: Data fetching service (creates default if None)
            indicator_service: Indicator calculation service (creates default if None)
            signal_service: Signal detection service (creates default if None)
            verdict_service: Verdict determination service (creates default if None)
            config: Strategy configuration (uses default if None)
        """
        self.config = config or StrategyConfig.default()
        
        # Dependency injection - allows for testing with mocks
        self.data_service = data_service or DataService()
        self.indicator_service = indicator_service or IndicatorService(self.config)
        self.signal_service = signal_service or SignalService(self.config)
        self.verdict_service = verdict_service or VerdictService(self.config)
    
    def analyze_ticker(
        self,
        ticker: str,
        enable_multi_timeframe: bool = True,
        export_to_csv: bool = False,
        csv_exporter: Optional[CSVExporter] = None,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single ticker - main entry point
        
        This method replaces the monolithic analyze_ticker() function from
        core/analysis.py with a clean pipeline approach.
        
        Args:
            ticker: Stock ticker symbol (e.g., "RELIANCE.NS")
            enable_multi_timeframe: Enable multi-timeframe analysis
            export_to_csv: Export results to CSV
            csv_exporter: CSV exporter instance (creates default if None)
            as_of_date: Date for analysis (YYYY-MM-DD format) - used for backtesting
            
        Returns:
            Dict with analysis results including:
            - ticker: str
            - verdict: str (strong_buy/buy/watch/avoid)
            - signals: List[str]
            - rsi: float
            - pe, pb: Optional[float]
            - buy_range, target, stop: Optional values
            - status: str (success/error)
        """
        try:
            logger.debug(f"Starting analysis for {ticker}")
            
            # Disable current day data addition during backtesting (when as_of_date is provided)
            add_current_day = as_of_date is None  # Only add current day for live analysis
            
            # Step 1: Fetch data
            df = None
            weekly_df = None
            
            if enable_multi_timeframe:
                multi_data = self.data_service.fetch_multi_timeframe(
                    ticker, end_date=as_of_date, add_current_day=add_current_day
                )
                if multi_data is None or multi_data.get('daily') is None:
                    logger.warning(f"No multi-timeframe data available for {ticker}")
                    return {"ticker": ticker, "status": "no_data"}
                df = multi_data['daily']
                weekly_df = multi_data.get('weekly')
            else:
                df = self.data_service.fetch_single_timeframe(
                    ticker, end_date=as_of_date, add_current_day=add_current_day
                )
                if df is None or df.empty:
                    logger.warning(f"No data available for {ticker}")
                    return {"ticker": ticker, "status": "no_data"}
            
            # Step 2: Clip to as_of_date if provided (ensure no future data leaks)
            df = self.data_service.clip_to_date(df, as_of_date)
            if weekly_df is not None:
                weekly_df = self.data_service.clip_to_date(weekly_df, as_of_date)
            
            # Step 3: Compute technical indicators
            df = self.indicator_service.compute_indicators(df)
            if df is None or df.empty:
                logger.error(f"Failed to compute indicators for {ticker}")
                return {"ticker": ticker, "status": "indicator_error"}
            
            # Step 4: Get latest and previous rows
            last = self.data_service.get_latest_row(df)
            prev = self.data_service.get_previous_row(df)
            
            if last is None:
                logger.error(f"Error accessing data rows for {ticker}")
                return {"ticker": ticker, "status": "data_access_error"}
            
            # Step 5: Detect signals
            signal_data = self.signal_service.detect_all_signals(
                ticker=ticker,
                df=df,
                last=last,
                prev=prev,
                weekly_df=weekly_df,
                as_of_date=as_of_date
            )
            
            signals = signal_data['signals']
            timeframe_confirmation = signal_data['timeframe_confirmation']
            news_sentiment = signal_data['news_sentiment']
            
            # Step 6: Assess volume
            volume_data = self.verdict_service.assess_volume(df, last)
            
            # Step 7: Get recent extremes
            extremes = self.data_service.get_recent_extremes(df)
            
            # Step 8: Fetch fundamentals
            fundamentals = self.verdict_service.fetch_fundamentals(ticker)
            pe = fundamentals['pe']
            pb = fundamentals['pb']
            fundamental_ok = not (pe is not None and pe < 0)
            
            # Step 9: Get indicator values
            rsi_value = self.indicator_service.get_rsi_value(last)
            is_above_ema200 = self.indicator_service.is_above_ema200(last)
            
            # Step 10: Determine verdict
            verdict, justification = self.verdict_service.determine_verdict(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=volume_data['vol_ok'],
                vol_strong=volume_data['vol_strong'],
                fundamental_ok=fundamental_ok,
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment
            )
            
            # Step 11: Apply candle quality check (may downgrade verdict)
            verdict, candle_analysis, downgrade_reason = self.verdict_service.apply_candle_quality_check(
                df, verdict
            )
            if downgrade_reason:
                justification.append(f"candle_downgrade:{downgrade_reason}")
            
            # Step 12: Calculate trading parameters
            current_price = float(last['close'])
            trading_params = self.verdict_service.calculate_trading_parameters(
                current_price=current_price,
                verdict=verdict,
                recent_low=extremes['low'],
                recent_high=extremes['high'],
                timeframe_confirmation=timeframe_confirmation,
                df=df
            )
            
            # Step 13: Build result
            result = {
                "ticker": ticker,
                "verdict": verdict,
                "signals": signals,
                "rsi": round(rsi_value, 2) if rsi_value is not None else None,
                "avg_vol": int(volume_data['avg_vol']),
                "today_vol": int(volume_data['today_vol']),
                "pe": pe,
                "pb": pb,
                "buy_range": trading_params['buy_range'] if trading_params is not None else None,
                "target": trading_params['target'] if trading_params is not None else None,
                "stop": trading_params['stop'] if trading_params is not None else None,
                "justification": justification,
                "last_close": round(current_price, 2),
                "timeframe_analysis": timeframe_confirmation,
                "news_sentiment": news_sentiment,
                "volume_analysis": volume_data['volume_analysis'],
                "volume_pattern": volume_data['volume_pattern'],
                "volume_description": volume_data['volume_description'],
                "candle_analysis": candle_analysis,
                "status": "success"
            }
            
            logger.debug(f"Analysis completed successfully for {ticker}: {verdict}")
            
            # Step 14: Export to CSV if requested
            if export_to_csv:
                if csv_exporter is None:
                    csv_exporter = CSVExporter()
                
                # Export individual stock analysis
                csv_exporter.export_single_stock(result)
                
                # Also append to master CSV for historical tracking
                csv_exporter.append_to_master_csv(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error in analyze_ticker for {ticker}: {type(e).__name__}: {e}")
            return {"ticker": ticker, "status": "analysis_error", "error": str(e)}

