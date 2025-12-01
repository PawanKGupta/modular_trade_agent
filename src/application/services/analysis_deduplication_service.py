"""Analysis Deduplication Service

Handles deduplication of analysis results based on trading day windows.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.signals_repository import SignalsRepository

# Constants
WEEKEND_START_WEEKDAY = 5  # Saturday


class AnalysisDeduplicationService:
    """Service for deduplicating analysis results based on trading day windows"""

    def __init__(self, db: Session):
        self.db = db
        self._signals_repo = SignalsRepository(db)

    def get_current_trading_day_window(self) -> tuple[datetime, datetime]:
        """
        Get the current trading day window (9AM to next day 9AM, excluding weekends).

        Trading day logic:
        - If current time >= 9AM today -> trading day = today
        - If current time < 9AM today -> trading day = previous trading day (skip weekends)
        - If today is weekend -> trading day = last Friday

        Returns:
            (window_start: datetime, window_end: datetime)
        """
        now = ist_now()
        current_time = now.time()
        current_date = now.date()

        # If before 9AM, use previous trading day
        if current_time < time(9, 0):
            # Go back to previous trading day (skip weekends)
            trading_day = current_date - timedelta(days=1)
            while trading_day.weekday() >= WEEKEND_START_WEEKDAY:  # Saturday = 5, Sunday = 6
                trading_day -= timedelta(days=1)
            window_start = datetime.combine(trading_day, time(9, 0))
            window_end = datetime.combine(current_date, time(9, 0))
        else:
            # Current trading day
            window_start = datetime.combine(current_date, time(9, 0))
            window_end = datetime.combine(current_date + timedelta(days=1), time(9, 0))

        return window_start, window_end

    def is_weekend_or_holiday(self, check_date: date | None = None) -> bool:
        """
        Check if a date is weekend or holiday.

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            True if weekend/holiday, False otherwise
        """
        if check_date is None:
            check_date = ist_now().date()

        # Check if weekend
        weekday = check_date.weekday()
        if weekday >= WEEKEND_START_WEEKDAY:  # Saturday or Sunday
            return True

        # TODO: Add holiday checking logic if needed
        # For now, just check weekday

        return False

    def should_update_signals(self) -> bool:
        """
        Check if signals should be updated.

        Update rules:
        - Weekend/Holiday: Allow before 9AM (part of previous trading day), block after 9AM
        - Weekday: Block between 9AM-4PM (during trading hours), allow before 9AM or after 4PM

        Examples:
        - Run at 4PM today -> 9AM tomorrow: Stocks are part of today (allowed)
        - Run between 9AM-4PM today: Skip update (during trading hours)
        - Run before 9AM: Allow (can update for previous day)

        Returns:
            True if should update, False otherwise
        """
        now = ist_now()
        current_time = now.time()
        current_date = now.date()

        # Weekend/Holiday logic
        if self.is_weekend_or_holiday(current_date):
            # Check if it's before 9AM on weekend (part of previous trading day)
            if current_time < time(9, 0):
                # Before 9AM on weekend, still part of previous trading day
                return True
            else:
                # After 9AM on weekend, don't update
                return False

        # Weekday logic
        # Block updates between 9AM-4PM (during trading hours)
        if time(9, 0) <= current_time < time(16, 0):
            return False

        # Allow updates before 9AM (previous day) or after 4PM (current day)
        return True

    def deduplicate_and_update_signals(
        self, new_signals: list[dict], skip_time_check: bool = False
    ) -> dict[str, int]:
        """
        Update existing signals or insert new ones based on trading day window.

        Args:
            new_signals: List of signal dictionaries from analysis
            skip_time_check: If True, skip the should_update_signals() check (already checked upstream)

        Returns:
            dict with 'updated' and 'inserted' counts
        """
        if not skip_time_check and not self.should_update_signals():
            return {"updated": 0, "inserted": 0, "skipped": len(new_signals)}

        window_start, window_end = self.get_current_trading_day_window()

        # Get existing signals in window
        stmt = select(Signals).where(
            Signals.ts >= window_start,
            Signals.ts < window_end,
        )
        existing_signals = list(self.db.execute(stmt).scalars().all())
        existing_symbols = {s.symbol for s in existing_signals}

        updated_count = 0
        inserted_count = 0
        skipped_count = 0

        for signal_data in new_signals:
            symbol = signal_data.get("symbol") or signal_data.get("ticker", "").replace(".NS", "")
            if not symbol:
                skipped_count += 1
                continue

            try:
                if symbol in existing_symbols:
                    # Update existing signal
                    existing = next(s for s in existing_signals if s.symbol == symbol)
                    self._update_signal_from_data(existing, signal_data)
                    updated_count += 1
                else:
                    # Insert new signal
                    new_signal = self._create_signal_from_data(signal_data)
                    if new_signal:
                        self.db.add(new_signal)
                        inserted_count += 1
                    else:
                        skipped_count += 1
            except Exception as signal_error:
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Error processing signal for {symbol}: {signal_error}",
                    exc_info=signal_error,
                )
                skipped_count += 1

        try:
            self.db.commit()
        except Exception as commit_error:
            self.db.rollback()
            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to commit signals to database: {commit_error}",
                exc_info=commit_error,
            )
            raise RuntimeError(
                f"Failed to commit signals to database: {commit_error}"
            ) from commit_error

        return {
            "updated": updated_count,
            "inserted": inserted_count,
            "skipped": skipped_count,
        }

    @staticmethod
    def _convert_boolean(value: object) -> bool | None:
        """Convert string boolean to actual boolean"""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    @staticmethod
    def _convert_fundamental_assessment(value: object) -> str | None:
        """Convert fundamental_assessment to string (max 64 chars)"""
        if value is None:
            return None
        if isinstance(value, dict):
            result = value.get("fundamental_reason") or json.dumps(value)
        else:
            result = str(value)
        if len(result) > 64:
            result = result[:61] + "..."
        return result

    def _update_signal_from_data(self, signal: Signals, data: dict) -> None:
        """Update existing signal from analysis data"""
        if "rsi10" in data:
            signal.rsi10 = data["rsi10"]
        if "ema9" in data:
            signal.ema9 = data["ema9"]
        if "ema200" in data:
            signal.ema200 = data["ema200"]
        if "distance_to_ema9" in data:
            signal.distance_to_ema9 = data["distance_to_ema9"]
        if "clean_chart" in data:
            signal.clean_chart = self._convert_boolean(data["clean_chart"])
        if "monthly_support_dist" in data:
            signal.monthly_support_dist = data["monthly_support_dist"]
        if "confidence" in data:
            signal.confidence = data["confidence"]
        if "backtest_score" in data:
            signal.backtest_score = data["backtest_score"]
        if "combined_score" in data:
            signal.combined_score = data["combined_score"]
        if "strength_score" in data:
            signal.strength_score = data["strength_score"]
        if "priority_score" in data:
            signal.priority_score = data["priority_score"]
        if "ml_verdict" in data:
            signal.ml_verdict = data["ml_verdict"]
        if "ml_confidence" in data:
            signal.ml_confidence = data["ml_confidence"]
        if "ml_probabilities" in data:
            signal.ml_probabilities = data["ml_probabilities"]
        if "buy_range" in data:
            signal.buy_range = data["buy_range"]
        if "target" in data:
            signal.target = data["target"]
        if "stop" in data:
            signal.stop = data["stop"]
        if "last_close" in data:
            signal.last_close = data["last_close"]
        if "pe" in data:
            signal.pe = data["pe"]
        if "pb" in data:
            signal.pb = data["pb"]
        if "fundamental_assessment" in data:
            # Convert dict to string (fundamental_assessment is String(64), not JSON)
            value = data["fundamental_assessment"]
            if isinstance(value, dict):
                # Extract reason if available, otherwise convert to JSON string
                value = value.get("fundamental_reason") or json.dumps(value)
                # Truncate to 64 chars if needed
                if len(value) > 64:
                    value = value[:61] + "..."
            elif value is not None:
                value = str(value)[:64]  # Truncate to 64 chars
            signal.fundamental_assessment = value
        if "fundamental_ok" in data:
            signal.fundamental_ok = self._convert_boolean(data["fundamental_ok"])
        if "avg_vol" in data:
            signal.avg_vol = data["avg_vol"]
        if "today_vol" in data:
            signal.today_vol = data["today_vol"]
        if "volume_analysis" in data:
            signal.volume_analysis = data["volume_analysis"]
        if "volume_pattern" in data:
            signal.volume_pattern = data["volume_pattern"]
        if "volume_description" in data:
            signal.volume_description = data["volume_description"]
        if "vol_ok" in data:
            signal.vol_ok = self._convert_boolean(data["vol_ok"])
        if "volume_ratio" in data:
            signal.volume_ratio = data["volume_ratio"]
        if "verdict" in data:
            signal.verdict = data["verdict"]
        if "signals" in data:
            signal.signals = data["signals"]
        if "justification" in data:
            signal.justification = data["justification"]
        if "timeframe_analysis" in data:
            signal.timeframe_analysis = data["timeframe_analysis"]
        if "news_sentiment" in data:
            signal.news_sentiment = data["news_sentiment"]
        if "candle_analysis" in data:
            signal.candle_analysis = data["candle_analysis"]
        if "chart_quality" in data:
            signal.chart_quality = data["chart_quality"]
        if "final_verdict" in data:
            signal.final_verdict = data["final_verdict"]
        if "rule_verdict" in data:
            signal.rule_verdict = data["rule_verdict"]
        if "verdict_source" in data:
            signal.verdict_source = data["verdict_source"]
        if "backtest_confidence" in data:
            signal.backtest_confidence = data["backtest_confidence"]
        if "vol_strong" in data:
            signal.vol_strong = self._convert_boolean(data["vol_strong"])
        if "is_above_ema200" in data:
            signal.is_above_ema200 = self._convert_boolean(data["is_above_ema200"])
        if "dip_depth_from_20d_high_pct" in data:
            signal.dip_depth_from_20d_high_pct = data["dip_depth_from_20d_high_pct"]
        if "consecutive_red_days" in data:
            signal.consecutive_red_days = data["consecutive_red_days"]
        if "dip_speed_pct_per_day" in data:
            signal.dip_speed_pct_per_day = data["dip_speed_pct_per_day"]
        if "decline_rate_slowing" in data:
            signal.decline_rate_slowing = self._convert_boolean(data["decline_rate_slowing"])
        if "volume_green_vs_red_ratio" in data:
            signal.volume_green_vs_red_ratio = data["volume_green_vs_red_ratio"]
        if "support_hold_count" in data:
            signal.support_hold_count = data["support_hold_count"]
        if "liquidity_recommendation" in data:
            signal.liquidity_recommendation = data["liquidity_recommendation"]
        if "trading_params" in data:
            signal.trading_params = data["trading_params"]

        # Update timestamp to current time
        signal.ts = ist_now()

    def _create_signal_from_data(self, data: dict) -> Signals | None:
        """Create new signal from analysis data"""
        symbol = data.get("symbol") or data.get("ticker", "").replace(".NS", "")
        if not symbol:
            return None

        signal = Signals(
            symbol=symbol,
            rsi10=data.get("rsi10"),
            ema9=data.get("ema9"),
            ema200=data.get("ema200"),
            distance_to_ema9=data.get("distance_to_ema9"),
            clean_chart=self._convert_boolean(data.get("clean_chart")),
            monthly_support_dist=data.get("monthly_support_dist"),
            confidence=data.get("confidence"),
            backtest_score=data.get("backtest_score"),
            combined_score=data.get("combined_score"),
            strength_score=data.get("strength_score"),
            priority_score=data.get("priority_score"),
            ml_verdict=data.get("ml_verdict"),
            ml_confidence=data.get("ml_confidence"),
            ml_probabilities=data.get("ml_probabilities"),
            buy_range=data.get("buy_range"),
            target=data.get("target"),
            stop=data.get("stop"),
            last_close=data.get("last_close"),
            pe=data.get("pe"),
            pb=data.get("pb"),
            fundamental_assessment=self._convert_fundamental_assessment(
                data.get("fundamental_assessment")
            ),
            fundamental_ok=self._convert_boolean(data.get("fundamental_ok")),
            avg_vol=data.get("avg_vol"),
            today_vol=data.get("today_vol"),
            volume_analysis=data.get("volume_analysis"),
            volume_pattern=data.get("volume_pattern"),
            volume_description=data.get("volume_description"),
            vol_ok=self._convert_boolean(data.get("vol_ok")),
            volume_ratio=data.get("volume_ratio"),
            verdict=data.get("verdict"),
            signals=data.get("signals"),
            justification=data.get("justification"),
            timeframe_analysis=data.get("timeframe_analysis"),
            news_sentiment=data.get("news_sentiment"),
            candle_analysis=data.get("candle_analysis"),
            chart_quality=data.get("chart_quality"),
            final_verdict=data.get("final_verdict"),
            rule_verdict=data.get("rule_verdict"),
            verdict_source=data.get("verdict_source"),
            backtest_confidence=data.get("backtest_confidence"),
            vol_strong=self._convert_boolean(data.get("vol_strong")),
            is_above_ema200=self._convert_boolean(data.get("is_above_ema200")),
            dip_depth_from_20d_high_pct=data.get("dip_depth_from_20d_high_pct"),
            consecutive_red_days=data.get("consecutive_red_days"),
            dip_speed_pct_per_day=data.get("dip_speed_pct_per_day"),
            decline_rate_slowing=self._convert_boolean(data.get("decline_rate_slowing")),
            volume_green_vs_red_ratio=data.get("volume_green_vs_red_ratio"),
            support_hold_count=data.get("support_hold_count"),
            liquidity_recommendation=data.get("liquidity_recommendation"),
            trading_params=data.get("trading_params"),
        )
        return signal
