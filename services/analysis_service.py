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
from core.feature_engineering import calculate_all_dip_features
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
            
            # Step 2: Ensure sufficient historical data for chart quality assessment
            # RECOMMENDATION 1: Fetch more historical data before signal date for chart quality
            # Chart quality needs at least 60 days, but early signals in backtest might not have enough
            # Solution: If using pre_fetched_daily, it should already have history (from backtest engine)
            # If not using pre_fetched_daily and we don't have enough data, fetch additional historical data
            min_days_for_chart_quality = 60
            chart_quality_lookback_days = 90  # Fetch 90 days before signal date for chart quality (extra buffer)
            
            if as_of_date:
                # For backtesting: Check if we have enough data before signal date
                df_clipped_to_signal = self.data_service.clip_to_date(df.copy(), as_of_date)
                days_available = len(df_clipped_to_signal)
                
                # If using pre_fetched_daily, it should already have history from backtest engine
                # Backtest engine fetches data going back before backtest start date (for EMA200)
                # So pre_fetched_daily should have enough history for early signals
                if days_available < min_days_for_chart_quality and pre_fetched_daily is None:
                    # Not enough data AND not using pre_fetched_daily - try to fetch more historical data
                    logger.warning(f"{ticker}: Insufficient data before {as_of_date} ({days_available} days < {min_days_for_chart_quality} days)")
                    logger.info(f"{ticker}: Attempting to fetch additional historical data for chart quality assessment...")
                    
                    try:
                        # Fetch additional historical data
                        from datetime import datetime, timedelta
                        from core.data_fetcher import fetch_ohlcv_yf
                        
                        # Fetch enough days to cover chart quality lookback
                        additional_data = fetch_ohlcv_yf(
                            ticker,
                            end_date=as_of_date,
                            add_current_day=False,
                            days=chart_quality_lookback_days
                        )
                        
                        if additional_data is not None and not additional_data.empty:
                            # Use the data that has more history
                            if len(additional_data) > days_available:
                                logger.info(f"{ticker}: Fetched {len(additional_data)} days of historical data for chart quality")
                                df = additional_data
                            else:
                                logger.warning(f"{ticker}: Additional fetch didn't provide more data, using available data")
                        else:
                            logger.warning(f"{ticker}: Could not fetch additional data, using available data")
                    except Exception as e:
                        logger.warning(f"{ticker}: Failed to fetch additional historical data: {e}, using available data")
                elif days_available < min_days_for_chart_quality and pre_fetched_daily is not None:
                    # Using pre_fetched_daily but still not enough data after clipping
                    # This means the backtest engine data doesn't have enough history before signal date
                    # This can happen for very early signals - log warning but proceed with available data
                    logger.warning(f"{ticker}: Pre-fetched data has insufficient history before {as_of_date} ({days_available} days < {min_days_for_chart_quality} days)")
                    logger.warning(f"{ticker}: Consider fetching more historical data in backtest engine for early signals")
                
                # Clip to signal date for chart quality assessment (prevents future data leak)
                df_for_chart_quality = self.data_service.clip_to_date(df.copy(), as_of_date)
                logger.debug(f"{ticker}: Clipped data to {as_of_date} for chart quality assessment (prevents future data leak)")
            else:
                # Live trading: Use full data
                df_for_chart_quality = df.copy()
                logger.debug(f"{ticker}: Using full data for chart quality (live trading - no clipping needed)")
            
            # Step 3: Check chart quality on data up to as_of_date (last 60 days BEFORE signal date)
            # Chart quality analysis uses .tail(60) which gets last 60 rows from dataframe
            # By clipping first, we ensure .tail(60) gets last 60 days BEFORE signal date (correct!)
            if len(df_for_chart_quality) >= min_days_for_chart_quality:
                chart_quality_data = self.verdict_service.assess_chart_quality(df_for_chart_quality)
                chart_quality_passed = chart_quality_data.get('passed', True)
                
                # Log chart quality result for debugging
                if not chart_quality_passed:
                    logger.info(f"{ticker}: Chart quality FAILED on data up to {as_of_date or 'latest'} ({len(df_for_chart_quality)} days) - {chart_quality_data.get('reason', 'Poor chart quality')}")
                else:
                    logger.debug(f"{ticker}: Chart quality PASSED on data up to {as_of_date or 'latest'} ({len(df_for_chart_quality)} days)")
            else:
                # Insufficient data even after trying to fetch more
                # Use available data with adjusted threshold (if we have at least 30 days)
                if len(df_for_chart_quality) >= 30:
                    logger.warning(f"{ticker}: Limited data for chart quality ({len(df_for_chart_quality)} days < {min_days_for_chart_quality} days) - assessing with available data")
                    chart_quality_data = self.verdict_service.assess_chart_quality(df_for_chart_quality)
                    chart_quality_passed = chart_quality_data.get('passed', True)
                    if not chart_quality_passed:
                        logger.info(f"{ticker}: Chart quality FAILED with limited data ({len(df_for_chart_quality)} days) - {chart_quality_data.get('reason', 'Poor chart quality')}")
                else:
                    # Very limited data - assume passed (early signals in backtest)
                    logger.warning(f"{ticker}: Very limited data for chart quality ({len(df_for_chart_quality)} days < 30 days) - assuming passed")
                    chart_quality_data = {
                        'passed': True,
                        'reason': f'Very limited data ({len(df_for_chart_quality)} days) - chart quality check skipped'
                    }
                    chart_quality_passed = True
            
            # Step 4: Use clipped data for analysis (same as chart quality assessment)
            df_for_analysis = df_for_chart_quality.copy()
            if weekly_df is not None:
                weekly_df = self.data_service.clip_to_date(weekly_df, as_of_date)
            
            # Step 5: Compute technical indicators (or use pre-calculated if available)
            # RECOMMENDATION 2: Align EMA200 calculation between backtest engine and analysis service
            # When using pre-fetched data from backtest engine, use EMA200 from that data to ensure consistency
            # EMA200 is calculated on full data (including history) in backtest engine, which is more accurate
            if pre_calculated_indicators is not None and 'rsi' in pre_calculated_indicators and 'ema200' in pre_calculated_indicators:
                # Use pre-calculated indicators if available (optimization for integrated backtest)
                # RECOMMENDATION 2: When we have pre-calculated indicators from backtest engine,
                # they were calculated on full data (including history), which is more accurate for EMA200
                # So we should use those values instead of recalculating on clipped data
                
                # Still compute indicators for other columns (volume indicators, etc.)
                df_for_analysis = self.indicator_service.compute_indicators(df_for_analysis)
                
                # Override with pre-calculated values from backtest engine (more accurate)
                rsi_col = f'rsi{self.config.rsi_period}'
                if rsi_col in df_for_analysis.columns and 'rsi' in pre_calculated_indicators:
                    # Update with pre-calculated RSI (signal date value from backtest engine)
                    df_for_analysis.iloc[-1, df_for_analysis.columns.get_loc(rsi_col)] = pre_calculated_indicators['rsi']
                    logger.debug(f"{ticker}: Using pre-calculated RSI={pre_calculated_indicators['rsi']:.2f} from backtest engine")
                
                if 'ema200' in df_for_analysis.columns and 'ema200' in pre_calculated_indicators:
                    # RECOMMENDATION 2: Use EMA200 from backtest engine (calculated on full data)
                    # This ensures consistency between backtest engine and analysis service
                    ema200_from_backtest = pre_calculated_indicators['ema200']
                    df_for_analysis.iloc[-1, df_for_analysis.columns.get_loc('ema200')] = ema200_from_backtest
                    logger.debug(f"{ticker}: Using pre-calculated EMA200={ema200_from_backtest:.2f} from backtest engine (aligned)")
                logger.debug(f"{ticker}: Using pre-calculated indicators from backtest engine (optimization + alignment)")
            else:
                # Compute indicators normally (live trading or when pre-calculated not available)
                df_for_analysis = self.indicator_service.compute_indicators(df_for_analysis)
                if df_for_analysis is None or df_for_analysis.empty:
                    logger.error(f"Failed to compute indicators for {ticker}")
                    return {"ticker": ticker, "status": "indicator_error"}
            
            # Use df_for_analysis for the rest of the analysis
            df = df_for_analysis
            
            # Step 5.5: Calculate ML enhanced dip-buying features
            # These features help ML distinguish between good dips vs dead cat bounces
            try:
                dip_features = calculate_all_dip_features(df)
                logger.debug(f"{ticker}: Calculated dip features: depth={dip_features['dip_depth_from_20d_high_pct']:.1f}%, consecutive_red={dip_features['consecutive_red_days']}, slowing={dip_features['decline_rate_slowing']}")
            except Exception as e:
                logger.warning(f"{ticker}: Failed to calculate dip features: {e}, using defaults")
                dip_features = {
                    'dip_depth_from_20d_high_pct': 0.0,
                    'consecutive_red_days': 0,
                    'dip_speed_pct_per_day': 0.0,
                    'decline_rate_slowing': False,
                    'volume_green_vs_red_ratio': 1.0,
                    'support_hold_count': 0
                }
            
            # Step 6: Early return if chart quality failed (hard filter)
            # This prevents any further processing including ML model predictions
            if not chart_quality_passed:
                logger.info(f"{ticker}: Chart quality FAILED (hard filter) - {chart_quality_data.get('reason', 'Poor chart quality')}")
                logger.info(f"{ticker}: Returning 'avoid' verdict immediately (chart quality filter)")
                return {
                    "ticker": ticker,
                    "status": "success",
                    "verdict": "avoid",
                    "justification": [f"Chart quality failed: {chart_quality_data.get('reason', 'Poor chart quality')}"],
                    "chart_quality": chart_quality_data,
                    "chart_quality_passed": False,  # Explicitly set for clarity
                    "rsi": None,
                    "last_close": float(df.iloc[-1]['close']) if len(df) > 0 else 0.0,
                }
            
            # Step 7: Get latest and previous rows
            last = self.data_service.get_latest_row(df)
            prev = self.data_service.get_previous_row(df)
            
            if last is None:
                logger.error(f"Error accessing data rows for {ticker}")
                return {"ticker": ticker, "status": "data_access_error"}
            
            # Step 8: Detect signals
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
            
            # Step 9: Get indicator values (needed for RSI-based volume adjustment)
            rsi_value = self.indicator_service.get_rsi_value(last)
            is_above_ema200 = self.indicator_service.is_above_ema200(last)
            
            # Step 10: Assess volume (includes execution capital calculation)
            # RELAXED VOLUME REQUIREMENTS (2025-11-09): Pass RSI for RSI-based volume threshold adjustment
            # For RSI < 30 (oversold), volume requirement is reduced to 0.5x
            volume_data = self.verdict_service.assess_volume(df, last, rsi_value=rsi_value)
            
            # Step 11: Get recent extremes
            extremes = self.data_service.get_recent_extremes(df)
            
            # Step 12: Fetch fundamentals
            fundamentals = self.verdict_service.fetch_fundamentals(ticker)
            pe = fundamentals['pe']
            pb = fundamentals['pb']
            
            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Assess fundamentals with flexible logic
            # - Keep negative PE filter for "avoid" (loss-making companies)
            # - But allow "watch" verdict for growth stocks (negative PE) if PB ratio is reasonable (< 5.0)
            fundamental_assessment = self.verdict_service.assess_fundamentals(pe, pb)
            fundamental_ok = fundamental_assessment.get('fundamental_ok', not (pe is not None and pe < 0))  # Backward compatibility
            
            # Step 13: Determine verdict (chart quality already checked at Step 3 - should be True here)
            # NOTE: If chart quality failed, we would have returned early at Step 5
            # Passing chart_quality_passed=True ensures ML model respects the filter
            verdict, justification = self.verdict_service.determine_verdict(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=volume_data['vol_ok'],
                vol_strong=volume_data['vol_strong'],
                fundamental_ok=fundamental_ok,  # Backward compatibility
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment,
                chart_quality_passed=chart_quality_passed,  # Should be True at this point (early return if False)
                fundamental_assessment=fundamental_assessment  # New: flexible fundamental assessment
            )
            
            # Step 12: Apply candle quality check (may downgrade verdict)
            verdict, candle_analysis, downgrade_reason = self.verdict_service.apply_candle_quality_check(
                df, verdict
            )
            if downgrade_reason:
                justification.append(f"candle_downgrade:{downgrade_reason}")
            
            # Step 13: Calculate trading parameters
            # CRITICAL REQUIREMENT (2025-11-09): RSI10 < 30 is a key requirement
            # Trading parameters are ONLY calculated when RSI < 30 (or RSI < 20 if below EMA200)
            current_price = float(last['close'])
            trading_params = self.verdict_service.calculate_trading_parameters(
                current_price=current_price,
                verdict=verdict,
                recent_low=extremes['low'],
                recent_high=extremes['high'],
                timeframe_confirmation=timeframe_confirmation,
                df=df,
                rsi_value=rsi_value,  # Pass RSI for validation
                is_above_ema200=is_above_ema200  # Pass EMA200 position for threshold selection
            )
            
            # Step 14: Build result
            # ML TRAINING DATA COLLECTION (2025-11-09): Include fundamental_assessment for ML training
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
                "trading_params": trading_params,  # Include full trading_params dict for validation
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
                # ML TRAINING DATA COLLECTION (2025-11-09): Add fundamental assessment and volume flags
                "fundamental_assessment": fundamental_assessment,  # For ML training
                "fundamental_ok": fundamental_ok,  # For ML training
                "vol_ok": volume_data.get('vol_ok', False),  # For ML training
                "vol_strong": volume_data.get('vol_strong', False),  # For ML training
                "is_above_ema200": is_above_ema200,  # For ML training
                # ML ENHANCED DIP FEATURES (2025-01-10): New features for dip-buying strategy
                "dip_depth_from_20d_high_pct": round(dip_features['dip_depth_from_20d_high_pct'], 2),
                "consecutive_red_days": dip_features['consecutive_red_days'],
                "dip_speed_pct_per_day": round(dip_features['dip_speed_pct_per_day'], 2),
                "decline_rate_slowing": dip_features['decline_rate_slowing'],
                "volume_green_vs_red_ratio": round(dip_features['volume_green_vs_red_ratio'], 2),
                "support_hold_count": dip_features['support_hold_count'],
                "status": "success"
            }
            
            # Step 15: Log ML model status (TEMPORARILY DISABLED - 2025-11-09)
            # ML model is loaded but not used for verdict determination
            # Using rule-based logic only until ML model is fully trained
            if hasattr(self.verdict_service, 'model_loaded') and self.verdict_service.model_loaded:
                # ML model is loaded but verdict is determined by rule-based logic
                # ML predictions are logged for training data collection
                logger.info(f"{ticker}: ML model loaded but using rule-based logic (ML not fully trained yet)")
                logger.debug(f"{ticker}: ML predictions logged for training data collection")
            
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
