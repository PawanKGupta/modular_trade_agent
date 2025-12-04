"""
Backtest Service

Integrates historical backtesting into the trading agent workflow.
Migrated from core/backtest_scoring.py to service layer (Phase 4).

This service provides backtest scoring based on historical performance
of the trading strategy.
"""

import warnings

warnings.filterwarnings("ignore")

from utils.logger import logger

# Import backtest functions from core (will be migrated incrementally)
try:
    from integrated_backtest import run_integrated_backtest

    BACKTEST_MODE = "integrated"
except ImportError as e:
    logger.warning(f"Integrated backtest not available: {e}, using simple backtest")
    run_integrated_backtest = None
    BACKTEST_MODE = "simple"

# Import helper functions from core (temporary, will be migrated)
# Phase 4.8: calculate_backtest_score moved to BacktestService method
from core.backtest_scoring import run_stock_backtest


class BacktestService:
    """
    Service for running backtests and calculating backtest scores

    Provides methods to:
    - Run backtests for individual stocks
    - Calculate backtest scores from results
    - Add backtest scores to analysis results

    This service wraps the core backtest scoring logic,
    providing dependency injection and better testability.
    """

    def __init__(self, default_years_back: int = 2, dip_mode: bool = False):
        """
        Initialize backtest service

        Args:
            default_years_back: Default number of years for backtesting
            dip_mode: Whether to use dip mode for backtesting
        """
        self.default_years_back = default_years_back
        self.dip_mode = dip_mode

    def calculate_backtest_score(
        self, backtest_results: dict, dip_mode: bool | None = None
    ) -> float:
        """
        Calculate a backtest score based on performance metrics.

        Phase 4.8: Migrated from core.backtest_scoring.calculate_backtest_score()
        to service layer for better testability and dependency injection.

        Score components:
        - Annualized return percentage (40%)
        - Win rate (40%)
        - Strategy vs buy-and-hold performance (20%)
        - No trade frequency penalty (quality over quantity for reversals)

        Enhanced with:
        - Mild confidence adjustment for very low sample sizes
        - Pure focus on reversal quality over entire backtest period

        Args:
            backtest_results: Backtest results dictionary
            dip_mode: Whether to use dip mode (uses instance default if None)

        Returns:
            Float score between 0-100
        """
        if dip_mode is None:
            dip_mode = self.dip_mode

        if not backtest_results or backtest_results.get("total_positions", 0) == 0:
            return 0.0

        try:
            # Calculate annualized return based on actual trading days
            total_return = backtest_results.get("total_return_pct", 0)
            total_trades = backtest_results.get("total_trades", 0)

            # Estimate average holding period (assume 15 days if no position data available)
            avg_holding_days = 15  # Default assumption
            if "full_results" in backtest_results and backtest_results["full_results"].get(
                "positions"
            ):
                positions = backtest_results["full_results"]["positions"]
                if positions:
                    total_days = 0
                    valid_positions = 0
                    for pos in positions:
                        if pos.get("entry_date") and pos.get("exit_date"):
                            from datetime import datetime

                            entry = datetime.strptime(pos["entry_date"], "%Y-%m-%d")
                            exit = datetime.strptime(pos["exit_date"], "%Y-%m-%d")
                            days = (exit - entry).days
                            total_days += days
                            valid_positions += 1
                    if valid_positions > 0:
                        avg_holding_days = total_days / valid_positions

            # For reversal strategy, use total return directly (avoid extreme annualization)
            # Reversals are about absolute performance over the backtest period
            effective_return = total_return

            # Component 1: Total Return (40% weight) - Focus on reversal performance quality
            # Scale: 0-10% -> 0-50 points, 10%+ -> 50-100 points (more appropriate for reversals)
            if effective_return <= 10:
                return_score = (effective_return / 10) * 50 * 0.4
            else:
                return_score = (50 + min((effective_return - 10) * 2.5, 50)) * 0.4

            # Component 2: Win Rate (40% weight) - High importance for reversal consistency
            win_rate = backtest_results.get("win_rate", 0)
            win_score = win_rate * 0.4

            # Component 3: Strategy vs Buy & Hold (20% weight)
            vs_buyhold = backtest_results.get("strategy_vs_buy_hold", 0)
            alpha_score = min(max(vs_buyhold + 50, 0), 100) * 0.2

            # No trade frequency component - quality over quantity for reversal strategy

            # Calculate base score (no trade frequency penalty)
            base_score = return_score + win_score + alpha_score

            # Enhancement 1: Mild confidence adjustment for reversal strategy
            confidence_factor = 1.0
            if total_trades < 3:  # Only penalize very low sample sizes
                confidence_factor = 0.8 + (total_trades / 10)  # 80-100% confidence (mild penalty)
                logger.debug(
                    f"Applied confidence adjustment: {confidence_factor:.2f} for {total_trades} trades"
                )

            # No recent performance boost - reversal quality is consistent over time
            recent_boost = 1.0

            # Apply enhancements (confidence adjustment only)
            total_score = base_score * confidence_factor

            logger.debug(
                f"Backtest score breakdown: Total Return={effective_return:.1f}% ({return_score:.1f}), "
                f"Win={win_rate:.1f}% ({win_score:.1f}), Alpha={alpha_score:.1f}, "
                f"Trades={total_trades}, Total={total_score:.1f}"
            )

            return min(total_score, 100.0)  # Cap at 100

        except Exception as e:
            logger.error(f"Error calculating backtest score: {e}")
            return 0.0

    def run_stock_backtest(
        self, stock_symbol: str, years_back: int | None = None, dip_mode: bool | None = None, config=None
    ) -> dict:
        """
        Run backtest for a stock using available method (integrated or simple).

        This method delegates to core.backtest_scoring.run_stock_backtest()
        while providing a service interface.

        Args:
            stock_symbol: Stock symbol (e.g., "RELIANCE.NS")
            years_back: Number of years to backtest (uses default if None)
            dip_mode: Whether to use dip mode (uses instance default if None)
            config: StrategyConfig instance (for ML-enabled backtests)

        Returns:
            Dict with backtest results and score
        """
        if years_back is None:
            years_back = self.default_years_back
        if dip_mode is None:
            dip_mode = self.dip_mode

        return run_stock_backtest(stock_symbol, years_back, dip_mode, config)

    def add_backtest_scores_to_results(
        self,
        stock_results: list[dict],
        years_back: int | None = None,
        dip_mode: bool | None = None,
        config=None,
    ) -> list[dict]:
        """
        Add backtest scores to existing stock analysis results.

        This method enhances stock results with historical performance data
        and recalculates combined scores.

        Args:
            stock_results: List of stock analysis results
            years_back: Years of historical data to analyze (uses default if None)
            dip_mode: Whether to use dip mode (uses instance default if None)

        Returns:
            Enhanced stock results with backtest scores
        """
        if years_back is None:
            years_back = self.default_years_back
        if dip_mode is None:
            dip_mode = self.dip_mode

        logger.info(f"Adding backtest scores for {len(stock_results)} stocks...")

        enhanced_results = []

        for i, stock_result in enumerate(stock_results, 1):
            try:
                ticker = stock_result.get("ticker", "Unknown")
                logger.info(f"Processing {i}/{len(stock_results)}: {ticker}")

                # Preserve initial ML predictions (2025-11-11)
                # Backtest may overwrite these, so save them first
                # Use dict access to preserve even if None/empty (vs .get() which might lose them)
                initial_ml_verdict = stock_result.get("ml_verdict", None)
                initial_ml_confidence = stock_result.get("ml_confidence", None)
                initial_ml_probabilities = stock_result.get("ml_probabilities", None)
                has_initial_ml = "ml_verdict" in stock_result  # Track if ML field exists

                logger.debug(
                    f"{ticker}: Preserved ML: verdict={initial_ml_verdict}, conf={initial_ml_confidence}"
                )

                # Run backtest for this stock
                # Use config from stock_result if available, otherwise use passed config
                stock_config = stock_result.get("_config") or config
                backtest_data = self.run_stock_backtest(ticker, years_back, dip_mode, config=stock_config)

                # Add backtest data to stock result
                stock_result["backtest"] = {
                    "score": backtest_data.get("backtest_score", 0),
                    "total_return_pct": backtest_data.get("total_return_pct", 0),
                    "win_rate": backtest_data.get("win_rate", 0),
                    "total_trades": backtest_data.get("total_trades", 0),
                    "vs_buy_hold": backtest_data.get("vs_buy_hold", 0),
                    "execution_rate": backtest_data.get("execution_rate", 0),
                }

                # Calculate combined score (50% current analysis + 50% backtest)
                current_score = stock_result.get("strength_score", 0)
                backtest_score = backtest_data.get("backtest_score", 0)

                # Use ScoringService for combined score calculation
                from config.strategy_config import StrategyConfig
                from services.scoring_service import ScoringService

                scoring_service = ScoringService(config=StrategyConfig.default())
                combined_score = scoring_service.compute_combined_score(
                    current_score=current_score,
                    backtest_score=backtest_score,
                    current_weight=0.5,
                    backtest_weight=0.5,
                )

                stock_result["combined_score"] = combined_score
                stock_result["backtest_score"] = backtest_score

                # Re-classify based on combined score and key metrics
                self._reclassify_with_backtest(stock_result, backtest_score, combined_score)

                # Restore initial ML predictions (2025-11-11)
                # Ensure live ML prediction is preserved (backtest may have overwritten it)
                # Restore if we had initial ML data (even if value was None)
                if has_initial_ml:
                    stock_result["ml_verdict"] = initial_ml_verdict
                    stock_result["ml_confidence"] = initial_ml_confidence
                    stock_result["ml_probabilities"] = initial_ml_probabilities
                    logger.info(
                        f"{ticker}: ? Restored initial ML: {initial_ml_verdict} ({initial_ml_confidence})"
                    )
                else:
                    logger.debug(f"{ticker}: No initial ML to restore")

                logger.debug(
                    f"{ticker}: Final values in dict: ml_verdict={stock_result.get('ml_verdict')}, ml_conf={stock_result.get('ml_confidence')}"
                )

                # Calculate trading parameters for ML-only buy/strong_buy signals
                # (Parameters might be missing if rules rejected but ML approved)
                ml_verdict = stock_result.get("ml_verdict")
                if ml_verdict in ["buy", "strong_buy"]:
                    if (
                        not stock_result.get("buy_range")
                        or not stock_result.get("target")
                        or not stock_result.get("stop")
                    ):
                        logger.info(
                            f"{ticker}: Calculating parameters for ML verdict: {ml_verdict}"
                        )

                        try:
                            from core.analysis import (
                                calculate_smart_buy_range,
                                calculate_smart_stop_loss,
                                calculate_smart_target,
                            )

                            current_price = stock_result.get("last_close")

                            # Fallback 1: Try to get from pre_fetched_df if available
                            if (
                                not current_price or current_price <= 0
                            ) and "pre_fetched_df" in stock_result:
                                try:
                                    pre_df = stock_result["pre_fetched_df"]
                                    if pre_df is not None and not pre_df.empty:
                                        current_price = float(pre_df["close"].iloc[-1])
                                        logger.debug(
                                            f"{ticker}: Got current_price from pre_fetched_df: {current_price}"
                                        )
                                except Exception as e:
                                    logger.debug(
                                        f"{ticker}: Failed to get price from pre_fetched_df: {e}"
                                    )

                            # Fallback 2: Try to get from stock_info if available
                            if (
                                not current_price or current_price <= 0
                            ) and "stock_info" in stock_result:
                                try:
                                    info = stock_result["stock_info"]
                                    if isinstance(info, dict):
                                        current_price = info.get("currentPrice") or info.get(
                                            "regularMarketPrice"
                                        )
                                        if current_price:
                                            logger.debug(
                                                f"{ticker}: Got current_price from stock_info: {current_price}"
                                            )
                                except Exception as e:
                                    logger.debug(
                                        f"{ticker}: Failed to get price from stock_info: {e}"
                                    )

                            if current_price and current_price > 0:
                                timeframe_confirmation = stock_result.get("timeframe_analysis")

                                # Calculate parameters
                                buy_range = calculate_smart_buy_range(
                                    current_price, timeframe_confirmation
                                )
                                recent_low = current_price * 0.92
                                recent_high = current_price * 1.15
                                stop = calculate_smart_stop_loss(
                                    current_price, recent_low, timeframe_confirmation, None
                                )
                                target = calculate_smart_target(
                                    current_price,
                                    stop,
                                    ml_verdict,
                                    timeframe_confirmation,
                                    recent_high,
                                )

                                stock_result["buy_range"] = buy_range
                                stock_result["target"] = target
                                stock_result["stop"] = stop

                                logger.info(
                                    f"{ticker}: ML parameters - Buy: {buy_range}, Target: {target}, Stop: {stop}"
                                )
                            else:
                                logger.warning(
                                    f"{ticker}: Cannot calculate parameters - current_price is missing or zero"
                                )
                                stock_result["buy_range"] = None
                                stock_result["target"] = None
                                stock_result["stop"] = None
                        except Exception as e:
                            logger.warning(f"{ticker}: Failed to calculate ML parameters: {e}")
                            # Set None to trigger filtering or special display
                            stock_result["buy_range"] = None
                            stock_result["target"] = None
                            stock_result["stop"] = None

                enhanced_results.append(stock_result)

            except Exception as e:
                logger.error(
                    f"Error adding backtest score for {stock_result.get('ticker', 'Unknown')}: {e}"
                )
                # Add stock without backtest score
                stock_result["backtest"] = {"score": 0, "error": str(e)}
                # Restore initial ML predictions even on error (2025-11-11)
                if "has_initial_ml" in locals() and has_initial_ml:
                    stock_result["ml_verdict"] = initial_ml_verdict
                    stock_result["ml_confidence"] = initial_ml_confidence
                    stock_result["ml_probabilities"] = initial_ml_probabilities
                    logger.debug(f"Restored ML after error for {ticker}")
                enhanced_results.append(stock_result)

        return enhanced_results

    def _reclassify_with_backtest(
        self, stock_result: dict, backtest_score: float, combined_score: float
    ) -> None:
        """
        Re-classify stock verdict based on backtest results.

        Args:
            stock_result: Stock analysis result (modified in place)
            backtest_score: Backtest score
            combined_score: Combined current + backtest score
        """
        # Get trade count for confidence assessment
        trade_count = stock_result.get("backtest", {}).get("total_trades", 0)

        # Get current RSI for dynamic threshold adjustment
        current_rsi = stock_result.get("rsi") or 30  # Default to 30 if None or not available

        # Ensure current_rsi is a number (handle None case)
        if current_rsi is None:
            current_rsi = 30

        # RSI-based threshold adjustment (more oversold = lower thresholds)
        rsi_factor = 1.0
        if current_rsi < 20:  # Extremely oversold
            rsi_factor = 0.7  # 30% lower thresholds
        elif current_rsi < 25:  # Very oversold
            rsi_factor = 0.8  # 20% lower thresholds
        elif current_rsi < 30:  # Oversold
            rsi_factor = 0.9  # 10% lower thresholds

        # Enhanced reclassification with confidence-aware and RSI-adjusted thresholds
        if trade_count >= 5:
            # High confidence thresholds (adjusted by RSI)
            strong_buy_threshold = 60 * rsi_factor
            combined_strong_threshold = 35 * rsi_factor
            combined_exceptional_threshold = 60 * rsi_factor

            buy_threshold = 35 * rsi_factor
            combined_buy_threshold = 22 * rsi_factor
            combined_decent_threshold = 35 * rsi_factor

            if (
                backtest_score >= strong_buy_threshold
                and combined_score >= combined_strong_threshold
            ) or combined_score >= combined_exceptional_threshold:
                stock_result["final_verdict"] = "strong_buy"
            elif (
                backtest_score >= buy_threshold and combined_score >= combined_buy_threshold
            ) or combined_score >= combined_decent_threshold:
                stock_result["final_verdict"] = "buy"
            else:
                stock_result["final_verdict"] = "watch"
        else:
            # Lower confidence thresholds (adjusted by RSI)
            strong_buy_threshold = 65 * rsi_factor
            combined_strong_threshold = 42 * rsi_factor
            combined_exceptional_threshold = 65 * rsi_factor

            buy_threshold = 40 * rsi_factor
            combined_buy_threshold = 28 * rsi_factor
            combined_decent_threshold = 45 * rsi_factor

            if (
                backtest_score >= strong_buy_threshold
                and combined_score >= combined_strong_threshold
            ) or combined_score >= combined_exceptional_threshold:
                stock_result["final_verdict"] = "strong_buy"
            elif (
                backtest_score >= buy_threshold and combined_score >= combined_buy_threshold
            ) or combined_score >= combined_decent_threshold:
                stock_result["final_verdict"] = "buy"
            else:
                stock_result["final_verdict"] = "watch"

        # Log RSI adjustment if applied
        if rsi_factor < 1.0:
            logger.debug(
                f"{stock_result.get('ticker', 'Unknown')}: RSI={current_rsi:.1f}, applied {(1 - rsi_factor) * 100:.0f}% threshold reduction"
            )

        # Add confidence indicator to result
        confidence_level = "High" if trade_count >= 5 else "Medium" if trade_count >= 2 else "Low"
        stock_result["backtest_confidence"] = confidence_level


# Backward compatibility functions
def calculate_backtest_score_compat(backtest_results: dict, dip_mode: bool = False) -> float:
    """
    Backward compatibility wrapper for core.backtest_scoring.calculate_backtest_score()
    """
    service = BacktestService(dip_mode=dip_mode)
    return service.calculate_backtest_score(backtest_results, dip_mode)


def run_stock_backtest_compat(
    stock_symbol: str, years_back: int = 2, dip_mode: bool = False
) -> dict:
    """
    Backward compatibility wrapper for core.backtest_scoring.run_stock_backtest()
    """
    service = BacktestService(default_years_back=years_back, dip_mode=dip_mode)
    return service.run_stock_backtest(stock_symbol, years_back, dip_mode)


def add_backtest_scores_to_results_compat(
    stock_results: list[dict], years_back: int = 2, dip_mode: bool = False
) -> list[dict]:
    """
    Backward compatibility wrapper for core.backtest_scoring.add_backtest_scores_to_results()
    """
    service = BacktestService(default_years_back=years_back, dip_mode=dip_mode)
    return service.add_backtest_scores_to_results(stock_results, years_back, dip_mode)
