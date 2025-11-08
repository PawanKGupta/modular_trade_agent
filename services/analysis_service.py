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
        
        # Two-Stage Approach: Use MLVerdictService if ML model is available
        # Stage 1: Chart quality filter (hard filter)
        # Stage 2: ML model prediction (only if chart quality passed)
        if verdict_service is None:
            # Try to use MLVerdictService if ML model is available
            try:
                from services.ml_verdict_service import MLVerdictService
                from pathlib import Path
                
                # Check if ML model exists
                ml_model_path = getattr(self.config, 'ml_verdict_model_path', 'models/verdict_model_random_forest.pkl')
                if Path(ml_model_path).exists():
                    self.verdict_service = MLVerdictService(model_path=ml_model_path, config=self.config)
                    if self.verdict_service.model_loaded:
                        logger.info(f"✅ Using MLVerdictService with model: {ml_model_path} (two-stage: chart quality + ML)")
                    else:
                        logger.warning(f"⚠️ ML model file exists but failed to load: {ml_model_path}, using VerdictService")
                        self.verdict_service = VerdictService(self.config)
                else:
                    self.verdict_service = VerdictService(self.config)
                    logger.debug(f"Using VerdictService (no ML model found at: {ml_model_path})")
            except Exception as e:
                logger.debug(f"Could not initialize MLVerdictService: {e}, using VerdictService")
                self.verdict_service = VerdictService(self.config)
        else:
            self.verdict_service = verdict_service
    
    def analyze_ticker(
        self,
        ticker: str,
        enable_multi_timeframe: bool = True,
        export_to_csv: bool = False,
        csv_exporter: Optional[CSVExporter] = None,
        as_of_date: Optional[str] = None,
        pre_fetched_daily: Optional[pd.DataFrame] = None,
        pre_fetched_weekly: Optional[pd.DataFrame] = None,
        pre_calculated_indicators: Optional[Dict[str, Any]] = None
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
            pre_fetched_daily: Optional pre-fetched daily DataFrame (avoids duplicate fetching)
            pre_fetched_weekly: Optional pre-fetched weekly DataFrame (avoids duplicate fetching)
            pre_calculated_indicators: Optional dict with pre-calculated indicators (rsi, ema200, etc.)
            
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
            
            # Step 1: Fetch data (or use pre-fetched data if available)
            df = None
            weekly_df = None
            
            # Use pre-fetched data if available (optimization for integrated backtest)
            if pre_fetched_daily is not None:
                df = pre_fetched_daily.copy()
                if enable_multi_timeframe and pre_fetched_weekly is not None:
                    weekly_df = pre_fetched_weekly.copy()
                logger.debug(f"Using pre-fetched data for {ticker} (optimization)")
            else:
                # Fetch data normally
                if enable_multi_timeframe:
                    multi_data = self.data_service.fetch_multi_timeframe(
                        ticker, end_date=as_of_date, add_current_day=add_current_day, config=self.config
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
            
            # Step 3: Compute technical indicators (or use pre-calculated if available)
            if pre_calculated_indicators is not None and 'rsi' in pre_calculated_indicators and 'ema200' in pre_calculated_indicators:
                # Use pre-calculated indicators if available (optimization for integrated backtest)
                # Still need to compute indicators for other columns, but can skip RSI/EMA200
                df = self.indicator_service.compute_indicators(df)
                # Override with pre-calculated values if they exist
                rsi_col = f'rsi{self.config.rsi_period}'
                if rsi_col in df.columns:
                    # Update with pre-calculated RSI (if available for the last row)
                    if 'rsi' in pre_calculated_indicators:
                        df.iloc[-1, df.columns.get_loc(rsi_col)] = pre_calculated_indicators['rsi']
                if 'ema200' in df.columns and 'ema200' in pre_calculated_indicators:
                    df.iloc[-1, df.columns.get_loc('ema200')] = pre_calculated_indicators['ema200']
                logger.debug(f"Using pre-calculated indicators for {ticker} (optimization)")
            else:
                # Compute indicators normally
                df = self.indicator_service.compute_indicators(df)
                if df is None or df.empty:
                    logger.error(f"Failed to compute indicators for {ticker}")
                    return {"ticker": ticker, "status": "indicator_error"}
            
            # Step 4: Check chart quality (hard filter) - early check to save processing
            chart_quality_data = self.verdict_service.assess_chart_quality(df)
            chart_quality_passed = chart_quality_data.get('passed', True)
            
            if not chart_quality_passed:
                logger.info(f"{ticker}: Chart quality failed - {chart_quality_data.get('reason', 'Poor chart quality')}")
                return {
                    "ticker": ticker,
                    "status": "success",
                    "verdict": "avoid",
                    "justification": [f"Chart quality failed: {chart_quality_data.get('reason', 'Poor chart quality')}"],
                    "chart_quality": chart_quality_data,
                    "rsi": None,
                    "last_close": float(df.iloc[-1]['close']) if len(df) > 0 else 0.0,
                }
            
            # Step 5: Get latest and previous rows
            last = self.data_service.get_latest_row(df)
            prev = self.data_service.get_previous_row(df)
            
            if last is None:
                logger.error(f"Error accessing data rows for {ticker}")
                return {"ticker": ticker, "status": "data_access_error"}
            
            # Step 6: Detect signals
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
            
            # Step 7: Assess volume (includes execution capital calculation)
            volume_data = self.verdict_service.assess_volume(df, last)
            
            # Step 8: Get recent extremes
            extremes = self.data_service.get_recent_extremes(df)
            
            # Step 9: Fetch fundamentals
            fundamentals = self.verdict_service.fetch_fundamentals(ticker)
            pe = fundamentals['pe']
            pb = fundamentals['pb']
            fundamental_ok = not (pe is not None and pe < 0)
            
            # Step 10: Get indicator values
            rsi_value = self.indicator_service.get_rsi_value(last)
            is_above_ema200 = self.indicator_service.is_above_ema200(last)
            
            # Step 11: Determine verdict (with chart quality check)
            verdict, justification = self.verdict_service.determine_verdict(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=volume_data['vol_ok'],
                vol_strong=volume_data['vol_strong'],
                fundamental_ok=fundamental_ok,
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment,
                chart_quality_passed=chart_quality_passed
            )
            
            # Step 12: Apply candle quality check (may downgrade verdict)
            verdict, candle_analysis, downgrade_reason = self.verdict_service.apply_candle_quality_check(
                df, verdict
            )
            if downgrade_reason:
                justification.append(f"candle_downgrade:{downgrade_reason}")
            
            # Step 13: Calculate trading parameters
            current_price = float(last['close'])
            trading_params = self.verdict_service.calculate_trading_parameters(
                current_price=current_price,
                verdict=verdict,
                recent_low=extremes['low'],
                recent_high=extremes['high'],
                timeframe_confirmation=timeframe_confirmation,
                df=df
            )
            
            # Step 14: Build result
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
                "chart_quality": chart_quality_data,
                "execution_capital": volume_data.get('execution_capital', 0.0),
                "max_capital": volume_data.get('max_capital', 0.0),
                "capital_adjusted": volume_data.get('capital_adjusted', False),
                "liquidity_recommendation": volume_data.get('liquidity_recommendation', {}),
                "status": "success"
            }
            
            # Step 15: Add ML verdict if using MLVerdictService (two-stage approach already enforced)
            # Note: ML verdict is already included in verdict if MLVerdictService is used
            # This is for tracking/debugging purposes
            if hasattr(self.verdict_service, 'model_loaded') and self.verdict_service.model_loaded:
                # ML verdict is already part of the verdict if MLVerdictService was used
                # Chart quality filtering is already enforced in determine_verdict()
                logger.debug(f"{ticker}: Using ML verdict service (two-stage: chart quality + ML)")
            
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

