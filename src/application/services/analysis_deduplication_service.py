"""Analysis Deduplication Service

Handles deduplication of analysis results based on trading day windows.
"""

from __future__ import annotations

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
        - If current time >= 9AM today → trading day = today
        - If current time < 9AM today → trading day = previous trading day (skip weekends)
        - If today is weekend → trading day = last Friday

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
        Check if signals should be updated (not weekend/holiday, and after 9AM).

        Returns:
            True if should update, False otherwise
        """
        now = ist_now()
        current_time = now.time()
        current_date = now.date()

        # Don't update on weekends/holidays
        if self.is_weekend_or_holiday(current_date):
            # Check if it's before 9AM on weekend (part of previous trading day)
            if current_time < time(9, 0):
                # Before 9AM on weekend, still part of previous trading day
                return True
            else:
                # After 9AM on weekend, don't update
                return False

        # Weekday: update if after 9AM
        return current_time >= time(9, 0)

    def deduplicate_and_update_signals(self, new_signals: list[dict]) -> dict[str, int]:
        """
        Update existing signals or insert new ones based on trading day window.

        Args:
            new_signals: List of signal dictionaries from analysis

        Returns:
            dict with 'updated' and 'inserted' counts
        """
        if not self.should_update_signals():
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

        for signal_data in new_signals:
            symbol = signal_data.get("symbol") or signal_data.get("ticker", "").replace(".NS", "")
            if not symbol:
                continue

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

        self.db.commit()
        return {
            "updated": updated_count,
            "inserted": inserted_count,
            "skipped": len(new_signals) - updated_count - inserted_count,
        }

    def _update_signal_from_data(self, signal: Signals, data: dict) -> None:
        """Update existing signal from analysis data"""
        # Update all fields from data
        if "rsi10" in data:
            signal.rsi10 = data["rsi10"]
        if "ema9" in data:
            signal.ema9 = data["ema9"]
        if "ema200" in data:
            signal.ema200 = data["ema200"]
        if "distance_to_ema9" in data:
            signal.distance_to_ema9 = data["distance_to_ema9"]
        if "clean_chart" in data:
            signal.clean_chart = data["clean_chart"]
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
            signal.fundamental_assessment = data["fundamental_assessment"]
        if "fundamental_ok" in data:
            signal.fundamental_ok = data["fundamental_ok"]
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
            signal.vol_ok = data["vol_ok"]
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
            clean_chart=data.get("clean_chart"),
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
            fundamental_assessment=data.get("fundamental_assessment"),
            fundamental_ok=data.get("fundamental_ok"),
            avg_vol=data.get("avg_vol"),
            today_vol=data.get("today_vol"),
            volume_analysis=data.get("volume_analysis"),
            volume_pattern=data.get("volume_pattern"),
            volume_description=data.get("volume_description"),
            vol_ok=data.get("vol_ok"),
            volume_ratio=data.get("volume_ratio"),
            verdict=data.get("verdict"),
            signals=data.get("signals"),
            justification=data.get("justification"),
            timeframe_analysis=data.get("timeframe_analysis"),
            news_sentiment=data.get("news_sentiment"),
            candle_analysis=data.get("candle_analysis"),
            chart_quality=data.get("chart_quality"),
        )
        return signal
