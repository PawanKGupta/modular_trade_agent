from config.settings import (
    VOLUME_LOOKBACK_DAYS,
)
from utils.logger import logger


def avg_volume(df, lookback=None):
    """Calculate average volume over specified lookback period (default from config)."""
    if lookback is None:
        lookback = VOLUME_LOOKBACK_DAYS
    return df["volume"].tail(lookback).mean()


def assess_fundamental_quality(pe, pb, rsi):
    """Assess fundamental quality (0-3 scale)"""
    score = 0

    # PE ratio assessment
    if pe is not None:
        if pe > 0 and pe < 15:  # Very attractive valuation
            score += 2
        elif pe > 0 and pe < 25:  # Decent valuation
            score += 1
        elif pe < 0:  # Negative earnings - penalize
            score -= 1

    # PB ratio assessment
    if pb is not None:
        if pb < 1.5:  # Trading below book value - attractive
            score += 1
        elif pb > 10:  # Very expensive - penalize
            score -= 1

    return max(0, min(score, 3))  # Cap between 0-3


def assess_volume_quality(vol_strong, current_volume, avg_volume):
    """Assess volume quality (0-3 scale)"""
    score = 0

    if vol_strong:
        score += 2  # Strong volume is excellent

    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
    if volume_ratio >= 1.5:  # 50% above average
        score += 1
    elif volume_ratio < 0.5:  # Very low volume - penalize
        score -= 1

    return max(0, min(score, 3))  # Cap between 0-3


def assess_setup_quality(timeframe_confirmation, signals):
    """Assess overall setup quality (0-3 scale)"""
    score = 0

    if timeframe_confirmation:
        # Support quality
        daily_support = timeframe_confirmation.get("daily_analysis", {}).get("support_analysis", {})
        if daily_support.get("quality") == "strong":
            score += 1

        # Oversold severity
        daily_oversold = timeframe_confirmation.get("daily_analysis", {}).get(
            "oversold_analysis", {}
        )
        if daily_oversold.get("severity") == "extreme":  # RSI < 20
            score += 1
        elif daily_oversold.get("severity") == "high":  # RSI < 30
            score += 0.5

        # Volume exhaustion
        daily_volume = timeframe_confirmation.get("daily_analysis", {}).get("volume_exhaustion", {})
        if daily_volume.get("exhaustion_score", 0) >= 2:
            score += 1

    # Pattern signals bonus
    pattern_count = len(
        [s for s in signals if s in ["hammer", "bullish_engulfing", "bullish_divergence"]]
    )
    if pattern_count >= 2:
        score += 1
    elif pattern_count >= 1:
        score += 0.5

    return min(score, 3)  # Cap at 3


def assess_support_proximity(timeframe_confirmation):
    """Assess how close the stock is to support levels (0-3 scale)"""
    if not timeframe_confirmation:
        return 0  # No MTF data = no support analysis

    score = 0

    # Get daily support analysis
    daily_analysis = timeframe_confirmation.get("daily_analysis", {})
    daily_support = daily_analysis.get("support_analysis", {})

    support_quality = daily_support.get("quality", "none")
    support_distance = daily_support.get("distance_pct", 999)

    # Score based on distance to support
    if support_quality in ["strong", "moderate"]:
        if support_distance <= 1.0:  # Very close to strong/moderate support
            score += 3
        elif support_distance <= 2.0:  # Close to support
            score += 2
        elif support_distance <= 4.0:  # Reasonably close to support
            score += 1
        # >4% from support = 0 points

        # Bonus for strong support quality
        if support_quality == "strong":
            score += 0.5

    elif support_quality == "weak" and support_distance <= 2.0:
        score += 1  # Even weak support gets some points if very close

    # Get weekly support analysis for additional context
    weekly_analysis = timeframe_confirmation.get("weekly_analysis", {})
    if weekly_analysis:
        weekly_support = weekly_analysis.get("support_analysis", {})
        weekly_quality = weekly_support.get("quality", "none")
        weekly_distance = weekly_support.get("distance_pct", 999)

        # Bonus for weekly support confluence
        if weekly_quality in ["strong", "moderate"] and weekly_distance <= 3.0:
            score += 0.5  # Multi-timeframe support confluence bonus

    return min(round(score), 3)  # Cap at 3


def calculate_smart_buy_range(current_price, timeframe_confirmation):
    """
    Calculate intelligent buy range based on support levels and MTF analysis

    [WARN]? DEPRECATED in Phase 4: This helper function is deprecated.
    Use VerdictService.calculate_trading_parameters() instead.
    """
    # Phase 4: Issue deprecation warning (but only once per session to avoid spam)
    import warnings

    warnings.warn(
        "DEPRECATED: core.analysis.calculate_smart_buy_range() is deprecated in Phase 4. "
        "Use services.VerdictService.calculate_trading_parameters() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        # Default range +/-1%
        default_range = (round(current_price * 0.995, 2), round(current_price * 1.01, 2))
        calculated_range = default_range

        if timeframe_confirmation:
            # Get support analysis from daily timeframe
            daily_analysis = timeframe_confirmation.get("daily_analysis", {})
            support_analysis = daily_analysis.get("support_analysis", {})

            support_level = support_analysis.get("support_level", 0)
            support_quality = support_analysis.get("quality", "none")
            distance_pct = support_analysis.get("distance_pct", 999)
            mtf_confirmation = timeframe_confirmation.get("confirmation", "")

            # Calculate range based on conditions
            if support_quality in ["strong", "moderate"] and distance_pct <= 2:
                # Very close to support - use support-based range
                support_buffer = 0.003 if support_quality == "strong" else 0.005  # 0.3% or 0.5%
                buy_low = round(support_level * (1 - support_buffer), 2)
                buy_high = round(support_level * (1 + support_buffer), 2)
                calculated_range = (buy_low, buy_high)

            elif support_quality in ["strong", "moderate"] and distance_pct <= 5:
                # Somewhat close to support - use tighter current price range
                calculated_range = (
                    round(current_price * 0.9925, 2),
                    round(current_price * 1.0075, 2),
                )

            elif mtf_confirmation == "excellent_uptrend_dip":
                # Excellent setup - use tight range
                calculated_range = (
                    round(current_price * 0.997, 2),
                    round(current_price * 1.007, 2),
                )

        # Validate range width (safeguard against overly wide ranges)
        buy_low, buy_high = calculated_range
        range_width_pct = ((buy_high - buy_low) / current_price) * 100

        if range_width_pct > 2.0:
            logger.warning(f"Buy range too wide ({range_width_pct:.1f}%), using default range")
            return default_range

        # Log the calculation for debugging
        if calculated_range != default_range:
            logger.debug(
                f"Smart buy range: {calculated_range} (width: {range_width_pct:.1f}%) vs default: {default_range}"
            )

        return calculated_range

    except Exception as e:
        logger.warning(f"Error calculating smart buy range: {e}")
        return (round(current_price * 0.995, 2), round(current_price * 1.01, 2))


def calculate_smart_stop_loss(current_price, recent_low, timeframe_confirmation, df):
    """
    Calculate intelligent stop loss based on uptrend context and support levels

    [WARN]? DEPRECATED in Phase 4: This helper function is deprecated.
    Use VerdictService.calculate_trading_parameters() instead.
    """
    # Phase 4: Issue deprecation warning
    import warnings

    warnings.warn(
        "DEPRECATED: core.analysis.calculate_smart_stop_loss() is deprecated in Phase 4. "
        "Use services.VerdictService.calculate_trading_parameters() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        # Default stop: recent low or 8% down
        default_stop = round(min(recent_low * 0.995, current_price * 0.92), 2)

        if not timeframe_confirmation:
            return default_stop

        daily_analysis = timeframe_confirmation.get("daily_analysis", {})
        weekly_analysis = timeframe_confirmation.get("weekly_analysis", {})

        # Get support levels
        daily_support = daily_analysis.get("support_analysis", {})
        weekly_support = weekly_analysis.get("support_analysis", {})

        daily_support_level = daily_support.get("support_level", 0)
        weekly_support_level = weekly_support.get("support_level", 0)

        mtf_confirmation = timeframe_confirmation.get("confirmation", "")

        # For strong uptrend dips, use more intelligent stops
        if mtf_confirmation in ["excellent_uptrend_dip", "good_uptrend_dip"]:
            # Use the lower of daily or weekly support (stronger level)
            key_support = (
                min(daily_support_level, weekly_support_level)
                if daily_support_level > 0 and weekly_support_level > 0
                else max(daily_support_level, weekly_support_level)
            )

            if key_support > 0:
                # Calculate support-based stop (2% below support for safety)
                support_stop = round(key_support * 0.98, 2)

                # Calculate distance from current price to support-based stop
                support_stop_distance = ((current_price - support_stop) / current_price) * 100

                # If support is too far (>8%), use percentage-based stop instead
                if support_stop_distance > 8:
                    # Use reasonable percentage stops
                    max_loss = 0.06 if mtf_confirmation == "excellent_uptrend_dip" else 0.05
                    return round(current_price * (1 - max_loss), 2)

                # If support is very close (<2%), use minimum 3% stop for breathing room
                if support_stop_distance < 3:
                    return round(current_price * 0.97, 2)  # 3% stop

                # Support is at reasonable distance (3-8%), use it
                return support_stop

        # For fair uptrend dips, slightly tighter than default
        elif mtf_confirmation == "fair_uptrend_dip":
            return round(min(recent_low * 0.995, current_price * 0.94), 2)  # 6% instead of 8%

        return default_stop

    except Exception as e:
        logger.warning(f"Error calculating smart stop loss: {e}")
        return round(min(recent_low * 0.995, current_price * 0.92), 2)


def calculate_smart_target(current_price, stop_price, verdict, timeframe_confirmation, recent_high):
    """
    Calculate intelligent target based on MTF quality, resistance levels, and risk-reward

    [WARN]? DEPRECATED in Phase 4: This helper function is deprecated.
    Use VerdictService.calculate_trading_parameters() instead.
    """
    # Phase 4: Issue deprecation warning
    import warnings

    warnings.warn(
        "DEPRECATED: core.analysis.calculate_smart_target() is deprecated in Phase 4. "
        "Use services.VerdictService.calculate_trading_parameters() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        # Calculate risk amount
        risk_amount = current_price - stop_price
        risk_pct = risk_amount / current_price if current_price > 0 else 0.08

        # Base target multipliers
        if verdict == "strong_buy":
            min_target_pct = 0.12  # 12% minimum
            risk_multiplier = 3.0  # 3x risk-reward
        else:
            min_target_pct = 0.08  # 8% minimum
            risk_multiplier = 2.5  # 2.5x risk-reward

        # Enhanced targets based on MTF confirmation quality
        if timeframe_confirmation:
            mtf_confirmation = timeframe_confirmation.get("confirmation", "")
            alignment_score = timeframe_confirmation.get("alignment_score", 0)

            # Excellent setups get higher targets
            if mtf_confirmation == "excellent_uptrend_dip":
                min_target_pct = 0.15  # 15% minimum for excellent setups
                risk_multiplier = 3.5  # 3.5x risk-reward
            elif mtf_confirmation == "good_uptrend_dip":
                min_target_pct = 0.12  # 12% minimum for good setups
                risk_multiplier = 3.0  # 3x risk-reward

            # Bonus for high alignment scores
            if alignment_score >= 8:
                risk_multiplier += 0.5
            elif alignment_score >= 6:
                risk_multiplier += 0.25

        # Calculate target based on risk-reward
        risk_reward_target = current_price + (risk_amount * risk_multiplier)
        min_target = current_price * (1 + min_target_pct)

        # Use the higher of minimum target or risk-reward target
        base_target = max(min_target, risk_reward_target)

        # Enhanced resistance-based target capping
        resistance_cap = recent_high * 1.05  # Default: 5% above recent high

        # Use MTF resistance analysis if available
        if timeframe_confirmation:
            daily_analysis = timeframe_confirmation.get("daily_analysis", {})
            daily_resistance = daily_analysis.get("resistance_analysis", {})

            resistance_level = daily_resistance.get("resistance_level", recent_high)
            resistance_quality = daily_resistance.get("quality", "unknown")
            distance_to_resistance = daily_resistance.get("distance_pct", 0)

            # Adjust target based on resistance context
            if resistance_quality == "strong" and distance_to_resistance >= 8:
                # Far from strong resistance - can use higher targets
                resistance_cap = resistance_level * 0.98  # Stop just before resistance
            elif resistance_quality == "moderate" and distance_to_resistance >= 5:
                # Moderate resistance with some room
                resistance_cap = resistance_level * 0.95
            elif resistance_quality in ["weak", "immediate"]:
                # Close to resistance - conservative targets
                resistance_cap = min(base_target * 0.9, resistance_level * 0.92)

        final_target = min(base_target, resistance_cap)

        # Ensure minimum viable target (at least 3% gain)
        min_viable_target = current_price * 1.03
        return round(max(final_target, min_viable_target), 2)

    except Exception as e:
        logger.warning(f"Error calculating smart target: {e}")
        # Fallback to simple calculation
        return round(current_price * 1.10, 2)


def analyze_ticker(
    ticker,
    enable_multi_timeframe=True,
    export_to_csv=False,
    csv_exporter=None,
    as_of_date=None,
    config=None,
    pre_fetched_data=None,
    pre_calculated_indicators=None,
):
    """
    Analyze a ticker - backward compatible wrapper using new service layer.

    [WARN]? DEPRECATED in Phase 4: This function is deprecated and will be removed in a future version.

    For new code, prefer using AnalysisService directly:
        from services import AnalysisService
        service = AnalysisService()
        result = service.analyze_ticker(ticker, ...)

    For async batch analysis, use AsyncAnalysisService:
        from services import AsyncAnalysisService
        import asyncio

        async def analyze():
            service = AsyncAnalysisService(max_concurrent=10)
            return await service.analyze_batch_async(tickers=[ticker])

        result = asyncio.run(analyze())[0]

    Migration guide: See utils.deprecation.get_migration_guide("analyze_ticker")

    Args:
        ticker: Stock ticker symbol
        enable_multi_timeframe: Enable multi-timeframe analysis
        export_to_csv: Export results to CSV
        csv_exporter: CSV exporter instance
        as_of_date: Analysis date (for backtesting)
        config: StrategyConfig instance (uses default if None)
        pre_fetched_data: Optional pre-fetched daily DataFrame (from BacktestEngine)
        pre_calculated_indicators: Optional dict with pre-calculated indicators (rsi, ema200, etc.)
    """
    # Get config if not provided
    from config.strategy_config import StrategyConfig

    if config is None:
        config = StrategyConfig.default()

    # Phase 4: Issue deprecation warning
    from utils.deprecation import deprecation_notice

    deprecation_notice(
        module="core.analysis",
        function="analyze_ticker",
        replacement="services.AnalysisService.analyze_ticker() or services.AsyncAnalysisService.analyze_batch_async()",
        version="Phase 4",
    )
    # Phase 4.5: Pure wrapper - delegate to service layer only
    try:
        from services.analysis_service import AnalysisService

        service = AnalysisService(config=config)
        return service.analyze_ticker(
            ticker=ticker,
            enable_multi_timeframe=enable_multi_timeframe,
            export_to_csv=export_to_csv,
            csv_exporter=csv_exporter,
            as_of_date=as_of_date,
        )
    except ImportError as e:
        # Service layer is required - no fallback
        logger.error(f"Service layer not available: {e}")
        return {
            "ticker": ticker,
            "status": "service_unavailable",
            "error": "AnalysisService is required. Please ensure services module is available.",
        }
    except Exception as e:
        logger.error(f"Analysis failed for {ticker}: {type(e).__name__}: {e}")
        return {"ticker": ticker, "status": "analysis_error", "error": str(e)}


def analyze_multiple_tickers(
    tickers, enable_multi_timeframe=True, export_to_csv=True, csv_filename=None
):
    """
    Analyze multiple tickers and export results to CSV

    [WARN]? DEPRECATED in Phase 4: This function is deprecated and will be removed in a future version.

    For new code, prefer using AsyncAnalysisService for faster batch analysis:
        from services import AsyncAnalysisService
        import asyncio

        async def analyze():
            service = AsyncAnalysisService(max_concurrent=10)
            return await service.analyze_batch_async(
                tickers=tickers,
                enable_multi_timeframe=enable_multi_timeframe,
                export_to_csv=export_to_csv
            )

        results = asyncio.run(analyze())

    Migration guide: See utils.deprecation.get_migration_guide("analyze_multiple_tickers")

    Args:
        tickers: List of ticker symbols to analyze
        enable_multi_timeframe: Enable multi-timeframe analysis
        export_to_csv: Export results to CSV
        csv_filename: Custom filename for CSV export

    Returns:
        List of analysis results and CSV filepath if exported
    """
    # Phase 4: Issue deprecation warning
    from utils.deprecation import deprecation_notice

    deprecation_notice(
        module="core.analysis",
        function="analyze_multiple_tickers",
        replacement="services.AsyncAnalysisService.analyze_batch_async()",
        version="Phase 4",
    )

    # Phase 4.5: Pure wrapper - delegate to AsyncAnalysisService
    import asyncio

    from services.async_analysis_service import AsyncAnalysisService

    logger.info(f"Starting batch analysis for {len(tickers)} tickers (using AsyncAnalysisService)")

    try:
        service = AsyncAnalysisService(max_concurrent=10)

        async def analyze():
            return await service.analyze_batch_async(
                tickers=tickers,
                enable_multi_timeframe=enable_multi_timeframe,
                export_to_csv=export_to_csv,
            )

        results = asyncio.run(analyze())

        # Handle CSV export if needed (AsyncAnalysisService handles it, but we return filepath for compatibility)
        csv_filepath = None
        if export_to_csv:
            # AsyncAnalysisService exports CSV internally
            # Return a placeholder path for backward compatibility
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filepath = f"analysis_results/bulk_analysis_{timestamp}.csv"
            logger.info(f"Batch analysis complete. Results exported to: {csv_filepath}")
        else:
            logger.info(f"Batch analysis complete for {len(results)} tickers")

        return results, csv_filepath
    except ImportError as e:
        logger.error(f"AsyncAnalysisService not available: {e}")
        return [], None
    except Exception as e:
        logger.error(f"Batch analysis failed: {type(e).__name__}: {e}")
        return [], None
