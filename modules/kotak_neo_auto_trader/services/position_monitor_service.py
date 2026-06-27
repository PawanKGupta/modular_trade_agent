# ruff: noqa: PLR0912, PLR0913, PLR0915, PLR0911, PLC0415, PLR2004
"""
Concrete implementation of PositionMonitorService.
"""

from typing import Any

from src.domain.interfaces.position_monitor_service import IPositionMonitorService
from src.infrastructure.db.timezone_utils import ist_now
from utils.logger import logger


class PositionMonitorService(IPositionMonitorService):
    """Concrete implementation of IPositionMonitorService."""

    def __init__(
        self,
        positions_repo=None,
        orders_repo=None,
        user_id=None,
        get_positions_repo=None,
        get_orders_repo=None,
        get_user_id=None,
    ):
        self._get_positions_repo = get_positions_repo
        self._get_orders_repo = get_orders_repo
        self._get_user_id = get_user_id

        self._positions_repo = positions_repo
        self._orders_repo = orders_repo
        self._user_id = user_id

    @property
    def positions_repo(self):
        if self._get_positions_repo:
            return self._get_positions_repo()
        return self._positions_repo

    @positions_repo.setter
    def positions_repo(self, value):
        self._positions_repo = value

    @property
    def orders_repo(self):
        if self._get_orders_repo:
            return self._get_orders_repo()
        return self._orders_repo

    @orders_repo.setter
    def orders_repo(self, value):
        self._orders_repo = value

    @property
    def user_id(self):
        if self._get_user_id:
            return self._get_user_id()
        return self._user_id

    @user_id.setter
    def user_id(self, value):
        self._user_id = value

    def _get_position_cycle_metadata(self, position: Any) -> dict[str, Any]:
        metadata = {
            "current_cycle": 0,
            "last_rsi_above_30": None,
            "last_rsi_value": None,
        }

        if not position or not position.reentries:
            return metadata

        # Check if reentries is a dict with _cycle_metadata key (new format)
        if isinstance(position.reentries, dict):
            cycle_meta = position.reentries.get("_cycle_metadata")
            if isinstance(cycle_meta, dict):
                metadata["current_cycle"] = cycle_meta.get("current_cycle", 0)
                metadata["last_rsi_above_30"] = cycle_meta.get("last_rsi_above_30")
                metadata["last_rsi_value"] = cycle_meta.get("last_rsi_value")
            return metadata

        return metadata

    def determine_reentry_level(
        self, entry_rsi: float, current_rsi: float, position: Any
    ) -> tuple[int | None, dict[str, Any]]:
        # Get current cycle metadata
        cycle_meta = self._get_position_cycle_metadata(position)
        current_cycle = cycle_meta.get("current_cycle", 0)
        last_rsi_above_30 = cycle_meta.get("last_rsi_above_30")
        last_rsi_value = cycle_meta.get("last_rsi_value")

        # Initialize metadata updates (None = no change)
        metadata_updates = {
            "current_cycle": None,
            "last_rsi_above_30": None,
            "last_rsi_value": None,
        }

        levels_taken = {"30": False, "20": False, "10": False}

        # Determine initial levels_taken based on entry_rsi
        if entry_rsi < 10:
            levels_taken = {"30": True, "20": True, "10": True}
        elif entry_rsi < 20:
            levels_taken = {"30": True, "20": True, "10": False}
        elif entry_rsi < 30:
            levels_taken = {"30": True, "20": False, "10": False}
        else:
            levels_taken = {"30": False, "20": False, "10": False}

        # Check reentries array to see which levels have been taken in the current cycle
        if position and position.reentries:
            reentries = position.reentries
            if isinstance(reentries, dict):
                reentries = reentries.get("reentries", [])
            if isinstance(reentries, list):
                for reentry in reentries:
                    if not isinstance(reentry, dict):
                        continue
                    reentry_cycle = reentry.get("cycle")
                    if reentry_cycle is not None:
                        if int(reentry_cycle) == current_cycle:
                            reentry_level = reentry.get("level")
                            if reentry_level is not None:
                                try:
                                    level_int = int(reentry_level)
                                    if level_int == 30:
                                        levels_taken["30"] = True
                                    elif level_int == 20:
                                        levels_taken["20"] = True
                                    elif level_int == 10:
                                        levels_taken["10"] = True
                                except (ValueError, TypeError):
                                    pass
                    elif current_cycle == 0:
                        reentry_level = reentry.get("level")
                        if reentry_level is not None:
                            try:
                                level_int = int(reentry_level)
                                if level_int == 30:
                                    levels_taken["30"] = True
                                elif level_int == 20:
                                    levels_taken["20"] = True
                                elif level_int == 10:
                                    levels_taken["10"] = True
                            except (ValueError, TypeError):
                                pass

        # Mark intermediate levels as taken to prevent backtracking
        if levels_taken.get("10"):
            levels_taken["20"] = True
            levels_taken["30"] = True
        elif levels_taken.get("20"):
            levels_taken["30"] = True

        # Enhanced reset detection with startup support
        if current_rsi > 30:
            now = ist_now()
            metadata_updates["last_rsi_above_30"] = now.isoformat()
            metadata_updates["last_rsi_value"] = current_rsi

        # Check for reset condition (RSI < 30 AND last_rsi_above_30 exists)
        if current_rsi < 30 and last_rsi_above_30:
            new_cycle = current_cycle + 1
            metadata_updates["current_cycle"] = new_cycle
            metadata_updates["last_rsi_above_30"] = None  # Clear reset flag
            metadata_updates["last_rsi_value"] = current_rsi  # Update last RSI value

            logger.info(
                f"Reset detected: RSI dropped to {current_rsi:.2f} after being above 30. "
                f"Incrementing cycle from {current_cycle} to {new_cycle}."
            )

            # Reset all levels, treat as new cycle
            levels_taken = {"30": False, "20": False, "10": False}

            if current_rsi < 10:
                logger.info(f"Reset triggers re-entry at level 10 (RSI {current_rsi:.2f} < 10)")
                return (10, metadata_updates)
            elif current_rsi < 20:
                logger.info(f"Reset triggers re-entry at level 20 (RSI {current_rsi:.2f} < 20)")
                return (20, metadata_updates)
            elif current_rsi < 30:
                logger.info(f"Reset triggers re-entry at level 30 (RSI {current_rsi:.2f} < 30)")
                return (30, metadata_updates)
            else:
                return (None, metadata_updates)

        # Update last_rsi_value if RSI changed (for tracking)
        if last_rsi_value != current_rsi:
            metadata_updates["last_rsi_value"] = current_rsi

        # Normal progression through levels
        next_level = None

        if current_rsi < 10:
            if not levels_taken.get("10"):
                next_level = 10
        elif current_rsi < 20:
            if not levels_taken.get("20"):
                next_level = 20
        elif current_rsi < 30:
            if not levels_taken.get("30"):
                next_level = 30

        return (next_level, metadata_updates)

    def has_reentry_at_level(self, base_symbol: str, level: int, allow_reset: bool = False) -> bool:
        try:
            if not self.positions_repo or not self.user_id:
                return False

            position = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
            if not position:
                return False

            cycle_meta = self._get_position_cycle_metadata(position)
            current_cycle = cycle_meta.get("current_cycle", 0)

            entry_rsi = position.entry_rsi
            if entry_rsi is not None and not allow_reset:
                if level == 30 and entry_rsi < 30:
                    return True
                elif level == 20 and entry_rsi < 20:
                    return True
                elif level == 10 and entry_rsi < 10:
                    return True

            if not position.reentries:
                return False

            reentries = position.reentries
            if isinstance(reentries, dict):
                reentries = reentries.get("reentries", [])
            if not isinstance(reentries, list):
                return False

            for reentry in reentries:
                if not isinstance(reentry, dict):
                    continue

                reentry_level = reentry.get("level")
                if reentry_level is None:
                    continue

                try:
                    reentry_level_int = int(reentry_level)
                    if reentry_level_int == level:
                        reentry_cycle = reentry.get("cycle")
                        if reentry_cycle is not None:
                            if int(reentry_cycle) == current_cycle:
                                return True
                        elif current_cycle == 0:
                            return True
                except (ValueError, TypeError):
                    continue

            return False
        except Exception as e:
            logger.error(f"Error checking reentry level for {base_symbol}: {e}")
            return False

    def has_reentry_at_level_today(self, base_symbol: str, level: int) -> bool:
        from modules.kotak_neo_auto_trader.reentry_day_guard import (
            has_reentry_at_level_today as reentry_today_check,
        )

        try:
            if not self.positions_repo or not self.user_id:
                return False

            position = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
            orders: list[Any] = []
            if self.orders_repo:
                orders_list, _ = self.orders_repo.list(self.user_id)
                orders = list(orders_list or [])

            return reentry_today_check(
                position=position,
                orders=orders,
                base_symbol=base_symbol,
                level=level,
                today=ist_now().date(),
            )
        except Exception as e:
            logger.error(f"Error checking same-day reentry level for {base_symbol}: {e}")
            return False
