"""
Analysis Service

Main orchestrator service that coordinates all analysis components.
This service replaces the monolithic analyze_ticker() function with a
clean, modular, testable architecture.
"""

from typing import Any

import pandas as pd

from config.strategy_config import StrategyConfig
from core.csv_exporter import CSVExporter
from core.feature_engineering import calculate_all_dip_features
from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.signal_service import SignalService
from services.verdict_service import VerdictService
from utils.logger import logger


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
        data_service: DataService | None = None,
        indicator_service: IndicatorService | None = None,
        signal_service: SignalService | None = None,
        verdict_service: VerdictService | None = None,
        config: StrategyConfig | None = None,
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

        # Two-Stage Approach: Use MLVerdictService if ML is enabled and model is available
        # Stage 1: Chart quality filter (hard filter)
        # Stage 2: ML model prediction (only if chart quality passed)
        if verdict_service is None:
            # Check if ML is enabled in config (respects UI setting)
            ml_enabled = getattr(self.config, "ml_enabled", False)

            # Debug logging to trace config value
            logger.debug(f"AnalysisService init: ml_enabled={ml_enabled}, config type={type(self.config)}, config.ml_enabled={getattr(self.config, 'ml_enabled', 'NOT_SET')}")

            if not ml_enabled:
                logger.debug("ML is disabled in config, using VerdictService")
                self.verdict_service = VerdictService(self.config)
            else:
                # Try to use MLVerdictService if ML is enabled
                try:
                    from pathlib import Path

                    from services.ml_verdict_service import MLVerdictService

                    # Get model path from config
                    ml_model_path = getattr(
                        self.config,
                        "ml_verdict_model_path",
                        "models/verdict_model_random_forest.pkl",
                    )

                    # Check if model path exists
                    if Path(ml_model_path).exists():
                        self.verdict_service = MLVerdictService(
                            model_path=ml_model_path, config=self.config
                        )
                        if self.verdict_service.model_loaded:
                            logger.info(
                                f"? Using MLVerdictService with model: {ml_model_path} (two-stage: chart quality + ML)"
                            )
                        else:
                            logger.warning(
                                f"[WARN]? ML model file exists but failed to load: {ml_model_path}, using VerdictService"
                            )
                            self.verdict_service = VerdictService(self.config)
                    else:
                        self.verdict_service = VerdictService(self.config)
                        logger.debug(
                            f"ML enabled but model not found at: {ml_model_path}, using VerdictService"
                        )
                except Exception as e:
                    logger.debug(
                        f"Could not initialize MLVerdictService: {e}, using VerdictService"
                    )
                    self.verdict_service = VerdictService(self.config)
        else:
            self.verdict_service = verdict_service

    def analyze_ticker(
        self,
        ticker: str,
        enable_multi_timeframe: bool = True,
        export_to_csv: bool = False,
        csv_exporter: CSVExporter | None = None,
        as_of_date: str | None = None,
        pre_fetched_daily: pd.DataFrame | None = None,
        pre_fetched_weekly: pd.DataFrame | None = None,
        pre_calculated_indicators: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            # Fetch data normally
            elif enable_multi_timeframe:
                multi_data = self.data_service.fetch_multi_timeframe(
                    ticker, end_date=as_of_date, add_current_day=add_current_day, config=self.config
                )
                if multi_data is None or multi_data.get("daily") is None:
                    logger.warning(f"No multi-timeframe data available for {ticker}")
                    return {"ticker": ticker, "status": "no_data"}
                df = multi_data["daily"]
                weekly_df = multi_data.get("weekly")
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
            chart_quality_lookback_days = (
                90  # Fetch 90 days before signal date for chart quality (extra buffer)
            )

            if as_of_date:
                # For backtesting: Check if we have enough data before signal date
                df_clipped_to_signal = self.data_service.clip_to_date(df.copy(), as_of_date)
                days_available = len(df_clipped_to_signal)

                # If using pre_fetched_daily, it should already have history from backtest engine
                # Backtest engine fetches data going back before backtest start date (for EMA200)
                # So pre_fetched_daily should have enough history for early signals
                if days_available < min_days_for_chart_quality and pre_fetched_daily is None:
                    # Not enough data AND not using pre_fetched_daily - try to fetch more historical data
                    logger.warning(
                        f"{ticker}: Insufficient data before {as_of_date} ({days_available} days < {min_days_for_chart_quality} days)"
                    )
                    logger.info(
                        f"{ticker}: Attempting to fetch additional historical data for chart quality assessment..."
                    )

                    try:
                        # Fetch additional historical data
                        from core.data_fetcher import fetch_ohlcv_yf

                        # Fetch enough days to cover chart quality lookback
                        additional_data = fetch_ohlcv_yf(
                            ticker,
                            end_date=as_of_date,
                            add_current_day=False,
                            days=chart_quality_lookback_days,
                        )

                        if additional_data is not None and not additional_data.empty:
                            # Use the data that has more history
                            if len(additional_data) > days_available:
                                logger.info(
                                    f"{ticker}: Fetched {len(additional_data)} days of historical data for chart quality"
                                )
                                df = additional_data
                            else:
                                logger.warning(
                                    f"{ticker}: Additional fetch didn't provide more data, using available data"
                                )
                        else:
                            logger.warning(
                                f"{ticker}: Could not fetch additional data, using available data"
                            )
                    except Exception as e:
                        logger.warning(
                            f"{ticker}: Failed to fetch additional historical data: {e}, using available data"
                        )
                elif days_available < min_days_for_chart_quality and pre_fetched_daily is not None:
                    # Using pre_fetched_daily but still not enough data after clipping
                    # This means the backtest engine data doesn't have enough history before signal date
                    # This can happen for very early signals - log warning but proceed with available data
                    logger.warning(
                        f"{ticker}: Pre-fetched data has insufficient history before {as_of_date} ({days_available} days < {min_days_for_chart_quality} days)"
                    )
                    logger.warning(
                        f"{ticker}: Consider fetching more historical data in backtest engine for early signals"
                    )

                # Clip to signal date for chart quality assessment (prevents future data leak)
                df_for_chart_quality = self.data_service.clip_to_date(df.copy(), as_of_date)
                logger.debug(
                    f"{ticker}: Clipped data to {as_of_date} for chart quality assessment (prevents future data leak)"
                )
            else:
                # Live trading: Use full data
                df_for_chart_quality = df.copy()
                logger.debug(
                    f"{ticker}: Using full data for chart quality (live trading - no clipping needed)"
                )

            # Step 3: Check chart quality on data up to as_of_date (last 60 days BEFORE signal date)
            # Chart quality analysis uses .tail(60) which gets last 60 rows from dataframe
            # By clipping first, we ensure .tail(60) gets last 60 days BEFORE signal date (correct!)
            if len(df_for_chart_quality) >= min_days_for_chart_quality:
                chart_quality_data = self.verdict_service.assess_chart_quality(df_for_chart_quality)
                chart_quality_passed = chart_quality_data.get("passed", True)

                # Log chart quality result for debugging
                if not chart_quality_passed:
                    logger.info(
                        f"{ticker}: Chart quality FAILED on data up to {as_of_date or 'latest'} ({len(df_for_chart_quality)} days) - {chart_quality_data.get('reason', 'Poor chart quality')}"
                    )
                else:
                    logger.debug(
                        f"{ticker}: Chart quality PASSED on data up to {as_of_date or 'latest'} ({len(df_for_chart_quality)} days)"
                    )
            # Insufficient data even after trying to fetch more
            # Use available data with adjusted threshold (if we have at least 30 days)
            elif len(df_for_chart_quality) >= 30:
                logger.warning(
                    f"{ticker}: Limited data for chart quality ({len(df_for_chart_quality)} days < {min_days_for_chart_quality} days) - assessing with available data"
                )
                chart_quality_data = self.verdict_service.assess_chart_quality(df_for_chart_quality)
                chart_quality_passed = chart_quality_data.get("passed", True)
                if not chart_quality_passed:
                    logger.info(
                        f"{ticker}: Chart quality FAILED with limited data ({len(df_for_chart_quality)} days) - {chart_quality_data.get('reason', 'Poor chart quality')}"
                    )
            else:
                # Very limited data - assume passed (early signals in backtest)
                logger.warning(
                    f"{ticker}: Very limited data for chart quality ({len(df_for_chart_quality)} days < 30 days) - assuming passed"
                )
                chart_quality_data = {
                    "passed": True,
                    "reason": f"Very limited data ({len(df_for_chart_quality)} days) - chart quality check skipped",
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
            if (
                pre_calculated_indicators is not None
                and "rsi" in pre_calculated_indicators
                and "ema200" in pre_calculated_indicators
            ):
                # Use pre-calculated indicators if available (optimization for integrated backtest)
                # RECOMMENDATION 2: When we have pre-calculated indicators from backtest engine,
                # they were calculated on full data (including history), which is more accurate for EMA200
                # So we should use those values instead of recalculating on clipped data

                # Still compute indicators for other columns (volume indicators, etc.)
                df_for_analysis = self.indicator_service.compute_indicators(df_for_analysis)

                # Override with pre-calculated values from backtest engine (more accurate)
                rsi_col = f"rsi{self.config.rsi_period}"
                if rsi_col in df_for_analysis.columns and "rsi" in pre_calculated_indicators:
                    # Update with pre-calculated RSI (signal date value from backtest engine)
                    df_for_analysis.iloc[-1, df_for_analysis.columns.get_loc(rsi_col)] = (
                        pre_calculated_indicators["rsi"]
                    )
                    logger.debug(
                        f"{ticker}: Using pre-calculated RSI={pre_calculated_indicators['rsi']:.2f} from backtest engine"
                    )

                if "ema200" in df_for_analysis.columns and "ema200" in pre_calculated_indicators:
                    # RECOMMENDATION 2: Use EMA200 from backtest engine (calculated on full data)
                    # This ensures consistency between backtest engine and analysis service
                    ema200_from_backtest = pre_calculated_indicators["ema200"]
                    df_for_analysis.iloc[-1, df_for_analysis.columns.get_loc("ema200")] = (
                        ema200_from_backtest
                    )
                    logger.debug(
                        f"{ticker}: Using pre-calculated EMA200={ema200_from_backtest:.2f} from backtest engine (aligned)"
                    )
                logger.debug(
                    f"{ticker}: Using pre-calculated indicators from backtest engine (optimization + alignment)"
                )
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
                # Safe logging - ensure values are numeric before formatting
                try:
                    depth = float(dip_features.get("dip_depth_from_20d_high_pct", 0))
                    red_days = int(dip_features.get("consecutive_red_days", 0))
                    slowing = bool(dip_features.get("decline_rate_slowing", False))
                    logger.debug(
                        f"{ticker}: Calculated dip features: depth={depth:.1f}%, consecutive_red={red_days}, slowing={slowing}"
                    )
                except (ValueError, TypeError, KeyError):
                    logger.debug(f"{ticker}: Calculated dip features (formatting skipped)")
            except Exception as e:
                logger.warning(f"{ticker}: Failed to calculate dip features: {e}, using defaults")
                dip_features = {
                    "dip_depth_from_20d_high_pct": 0.0,
                    "consecutive_red_days": 0,
                    "dip_speed_pct_per_day": 0.0,
                    "decline_rate_slowing": False,
                    "volume_green_vs_red_ratio": 1.0,
                    "support_hold_count": 0,
                }

            # Step 6: Early return if chart quality failed (hard filter)
            # This prevents any further processing including ML model predictions
            if not chart_quality_passed:
                logger.info(
                    f"{ticker}: Chart quality FAILED (hard filter) - {chart_quality_data.get('reason', 'Poor chart quality')}"
                )
                logger.info(
                    f"{ticker}: Returning 'avoid' verdict immediately (chart quality filter)"
                )
                return {
                    "ticker": ticker,
                    "status": "success",
                    "verdict": "avoid",
                    "justification": [
                        f"Chart quality failed: {chart_quality_data.get('reason', 'Poor chart quality')}"
                    ],
                    "chart_quality": chart_quality_data,
                    "chart_quality_passed": False,  # Explicitly set for clarity
                    "rsi": None,
                    "last_close": float(df.iloc[-1]["close"]) if len(df) > 0 else 0.0,
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
                as_of_date=as_of_date,
            )

            signals = signal_data["signals"]
            timeframe_confirmation = signal_data["timeframe_confirmation"]
            news_sentiment = signal_data["news_sentiment"]

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
            pe = fundamentals["pe"]
            pb = fundamentals["pb"]

            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Assess fundamentals with flexible logic
            # - Keep negative PE filter for "avoid" (loss-making companies)
            # - But allow "watch" verdict for growth stocks (negative PE) if PB ratio is reasonable (< 5.0)
            fundamental_assessment = self.verdict_service.assess_fundamentals(pe, pb)
            fundamental_ok = fundamental_assessment.get(
                "fundamental_ok", not (pe is not None and pe < 0)
            )  # Backward compatibility

            # Step 13: Determine verdict (chart quality already checked at Step 3 - should be True here)
            # NOTE: If chart quality failed, we would have returned early at Step 5
            # Passing chart_quality_passed=True ensures ML model respects the filter

            # Prepare indicators dict for ML prediction (includes enhanced dip features)
            indicators_for_ml = {
                "close": float(last["close"]),
                "rsi": rsi_value,
                "ema200": float(last.get("ema_200", 0)),
                "current_volume": float(last.get("volume", 0)),
                "avg_volume": volume_data.get("avg_volume", 0),
                **dip_features,  # Include all dip features for ML
            }

            verdict, justification = self.verdict_service.determine_verdict(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=volume_data["vol_ok"],
                vol_strong=volume_data["vol_strong"],
                fundamental_ok=fundamental_ok,  # Backward compatibility
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment,
                chart_quality_passed=chart_quality_passed,  # Should be True at this point (early return if False)
                fundamental_assessment=fundamental_assessment,  # New: flexible fundamental assessment
                indicators=indicators_for_ml,  # For ML prediction
                fundamentals=fundamentals,  # For ML prediction
                df=df,  # For ML prediction (enhanced features)
            )

            # Retrieve ML prediction info (if MLVerdictService is used and ML model is loaded)
            ml_prediction = None
            verdict_source = "rule_based"  # Default to rule-based
            if hasattr(self.verdict_service, "get_last_ml_prediction"):
                ml_prediction = self.verdict_service.get_last_ml_prediction()
                if ml_prediction:
                    # Safely format ML confidence (handle MagicMock in tests)
                    try:
                        ml_confidence = ml_prediction.get("ml_confidence")
                        if isinstance(ml_confidence, (int, float)):
                            confidence_str = f"{ml_confidence:.1%}"
                        else:
                            confidence_str = str(ml_confidence)
                        ml_verdict = ml_prediction.get("ml_verdict", "unknown")
                        logger.info(
                            f"{ticker}: ? ML prediction retrieved - {ml_verdict} ({confidence_str})"
                        )
                    except (TypeError, ValueError, AttributeError):
                        # Fallback if formatting fails (e.g., MagicMock in tests)
                        logger.info(
                            f"{ticker}: ? ML prediction retrieved - {ml_prediction.get('ml_verdict', 'unknown')}"
                        )

                    # Check if ML verdict was used (confidence >= threshold)
                    if hasattr(self.verdict_service, "ml_confidence_threshold"):
                        threshold = self.verdict_service.ml_confidence_threshold
                    else:
                        threshold = getattr(self.config, "ml_confidence_threshold", 0.5)

                    ml_confidence_val = ml_prediction.get("ml_confidence", 0)
                    if (
                        isinstance(ml_confidence_val, (int, float))
                        and ml_confidence_val >= threshold
                    ):
                        verdict_source = "ml"
                    else:
                        verdict_source = "rule_based"
                else:
                    logger.warning(f"{ticker}: [WARN]? ML prediction NOT available (returned None)")

            # Step 12: Apply candle quality check (may downgrade verdict)
            verdict, candle_analysis, downgrade_reason = (
                self.verdict_service.apply_candle_quality_check(df, verdict)
            )
            if downgrade_reason:
                justification.append(f"candle_downgrade:{downgrade_reason}")

            # Step 13: Calculate trading parameters
            # CRITICAL REQUIREMENT (2025-11-09): RSI10 < 30 is a key requirement
            # Trading parameters are ONLY calculated when RSI < 30 (or RSI < 20 if below EMA200)
            current_price = float(last["close"])
            trading_params = self.verdict_service.calculate_trading_parameters(
                current_price=current_price,
                verdict=verdict,
                recent_low=extremes["low"],
                recent_high=extremes["high"],
                timeframe_confirmation=timeframe_confirmation,
                df=df,
                rsi_value=rsi_value,  # Pass RSI for validation
                is_above_ema200=is_above_ema200,  # Pass EMA200 position for threshold selection
            )

            # Step 14: Extract EMA values and calculate distance
            ema9_value = None
            ema200_value = None
            distance_to_ema9 = None
            if "ema9" in last.index:
                ema9_val = last["ema9"]
                if ema9_val is not None and not (
                    isinstance(ema9_val, float) and (ema9_val != ema9_val)
                ):
                    ema9_value = round(float(ema9_val), 2)
                    if current_price > 0 and ema9_value > 0:
                        distance_to_ema9 = round(
                            ((ema9_value - current_price) / current_price) * 100, 2
                        )

            if "ema200" in last.index:
                ema200_val = last["ema200"]
                if ema200_val is not None and not (
                    isinstance(ema200_val, float) and (ema200_val != ema200_val)
                ):
                    ema200_value = round(float(ema200_val), 2)

            # Extract confidence from timeframe_analysis or ML confidence
            confidence_value = None
            if timeframe_confirmation and isinstance(timeframe_confirmation, dict):
                alignment_score = timeframe_confirmation.get("alignment_score")
                if alignment_score is not None:
                    confidence_value = float(alignment_score) / 10.0
            if confidence_value is None and ml_prediction:
                ml_conf = ml_prediction.get("ml_confidence")
                if isinstance(ml_conf, (int, float)):
                    confidence_value = float(ml_conf)

            # Step 15: Build result
            result = {
                "ticker": ticker,
                "verdict": verdict,
                "signals": signals,
                "rsi": round(rsi_value, 2) if rsi_value is not None else None,
                "rsi10": round(rsi_value, 2) if rsi_value is not None else None,
                "ema9": ema9_value,
                "ema200": ema200_value,
                "distance_to_ema9": distance_to_ema9,
                "confidence": confidence_value,
                "avg_vol": int(volume_data["avg_vol"]),
                "today_vol": int(volume_data["today_vol"]),
                "pe": pe,
                "pb": pb,
                "buy_range": trading_params["buy_range"] if trading_params is not None else None,
                "target": trading_params["target"] if trading_params is not None else None,
                "stop": trading_params["stop"] if trading_params is not None else None,
                "trading_params": trading_params,
                "justification": justification,
                "last_close": round(current_price, 2),
                "timeframe_analysis": timeframe_confirmation,
                "news_sentiment": news_sentiment,
                "volume_analysis": volume_data["volume_analysis"],
                "volume_pattern": volume_data["volume_pattern"],
                "volume_description": volume_data["volume_description"],
                "candle_analysis": candle_analysis,
                "chart_quality": chart_quality_data,
                "execution_capital": volume_data.get("execution_capital", 0.0),
                "max_capital": volume_data.get("max_capital", 0.0),
                "capital_adjusted": volume_data.get("capital_adjusted", False),
                "liquidity_recommendation": volume_data.get("liquidity_recommendation", {}),
                "fundamental_assessment": fundamental_assessment,
                "fundamental_ok": fundamental_ok,
                "vol_ok": volume_data.get("vol_ok", False),
                "vol_strong": volume_data.get("vol_strong", False),
                "is_above_ema200": is_above_ema200,
                "dip_depth_from_20d_high_pct": round(
                    float(dip_features.get("dip_depth_from_20d_high_pct", 0)), 2
                ),
                "consecutive_red_days": int(dip_features.get("consecutive_red_days", 0)),
                "dip_speed_pct_per_day": round(
                    float(dip_features.get("dip_speed_pct_per_day", 0)), 2
                ),
                "decline_rate_slowing": bool(dip_features.get("decline_rate_slowing", False)),
                "volume_green_vs_red_ratio": round(
                    float(dip_features.get("volume_green_vs_red_ratio", 1.0)), 2
                ),
                "support_hold_count": int(dip_features.get("support_hold_count", 0)),
                "ml_verdict": ml_prediction.get("ml_verdict") if ml_prediction else None,
                "ml_confidence": (
                    round(float(ml_prediction.get("ml_confidence", 0)) * 100, 1)
                    if ml_prediction
                    and isinstance(ml_prediction.get("ml_confidence"), (int, float))
                    else None
                ),
                "ml_probabilities": (
                    ml_prediction.get("ml_probabilities") if ml_prediction else None
                ),
                "rule_verdict": verdict,
                "verdict_source": verdict_source,
                "status": "success",
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

            # Store config in result for backtest to use (for ML support)
            # This allows backtest to use the same config that was used for analysis
            result['_config'] = self.config

            return result

        except Exception as e:
            logger.error(
                f"Unexpected error in analyze_ticker for {ticker}: {type(e).__name__}: {e}"
            )
            return {"ticker": ticker, "status": "analysis_error", "error": str(e)}
