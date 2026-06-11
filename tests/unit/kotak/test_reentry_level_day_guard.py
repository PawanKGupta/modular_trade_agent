"""
Tests for same-day same-level re-entry guard.

The guard blocks a second system re-entry at the same RSI level on the same IST
calendar day when that level already has a filled re-entry or a pending buy,
regardless of cycle increment (reset). Different levels on the same day remain allowed.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: E402
from modules.kotak_neo_auto_trader.reentry_day_guard import (  # noqa: E402
    has_reentry_at_level_today,
    reentry_level_used_today,
)
from src.infrastructure.db.models import OrderStatus as DbOrderStatus  # noqa: E402
from tests.ist_clock import ist_now  # noqa: E402
from tests.unit.kotak.conftest import assign_tradable_scrip_master  # noqa: E402


def _today_iso() -> str:
    return ist_now().date().isoformat()


def _yesterday_iso() -> str:
    return (ist_now().date() - timedelta(days=1)).isoformat()


class TestReentryLevelUsedTodayHelper:
    """Pure helper tests (no engine wiring)."""

    def test_filled_reentry_at_level_today_blocks_same_level(self):
        position = SimpleNamespace(
            reentries={
                "reentries": [
                    {
                        "level": 30,
                        "cycle": 1,
                        "qty": 10,
                        "placed_at": _today_iso(),
                    }
                ]
            }
        )
        assert reentry_level_used_today(position, level=30, today=ist_now().date()) is True

    def test_filled_reentry_yesterday_does_not_block_today(self):
        position = SimpleNamespace(
            reentries={
                "reentries": [
                    {
                        "level": 30,
                        "cycle": 1,
                        "qty": 10,
                        "placed_at": _yesterday_iso(),
                        "time": ist_now().isoformat(),
                    }
                ]
            }
        )
        assert reentry_level_used_today(position, level=30, today=ist_now().date()) is False

    def test_different_level_today_does_not_block(self):
        position = SimpleNamespace(
            reentries={
                "reentries": [
                    {
                        "level": 30,
                        "cycle": 0,
                        "qty": 10,
                        "placed_at": _today_iso(),
                    }
                ]
            }
        )
        assert reentry_level_used_today(position, level=20, today=ist_now().date()) is False

    def test_pending_reentry_order_at_level_today_blocks(self):
        order = SimpleNamespace(
            symbol="STAR-EQ",
            side="buy",
            status=DbOrderStatus.PENDING,
            execution_qty=None,
            placed_at=ist_now(),
            entry_type="reentry",
            order_metadata={"reentry_level": 30, "entry_type": "reentry"},
        )
        assert (
            has_reentry_at_level_today(
                position=None,
                orders=[order],
                base_symbol="STAR",
                level=30,
                today=ist_now().date(),
            )
            is True
        )

    def test_cancelled_reentry_order_today_does_not_block(self):
        order = SimpleNamespace(
            symbol="STAR-EQ",
            side="buy",
            status=DbOrderStatus.CANCELLED,
            execution_qty=None,
            placed_at=ist_now(),
            entry_type="reentry",
            order_metadata={"reentry_level": 30},
        )
        assert (
            has_reentry_at_level_today(
                position=None,
                orders=[order],
                base_symbol="STAR",
                level=30,
                today=ist_now().date(),
            )
            is False
        )

    def test_filled_order_today_blocks_before_reentries_array_updated(self):
        order = SimpleNamespace(
            symbol="STAR-EQ",
            side="buy",
            status=DbOrderStatus.CLOSED,
            execution_qty=10.0,
            placed_at=ist_now(),
            entry_type="reentry",
            order_metadata={"reentry_level": 30},
        )
        assert (
            has_reentry_at_level_today(
                position=SimpleNamespace(reentries=None),
                orders=[order],
                base_symbol="STAR",
                level=30,
                today=ist_now().date(),
            )
            is True
        )


@pytest.fixture
def reentry_engine():
    """Minimal AutoTradeEngine for place_reentry_orders day-guard tests."""
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
        engine = AutoTradeEngine(
            enable_verifier=False,
            enable_telegram=False,
            user_id=2,
            db_session=MagicMock(),
        )
        engine.user_id = 2
        engine.orders = Mock()
        engine.orders.get_pending_orders = Mock(return_value=[])
        engine.portfolio = Mock()
        engine.portfolio.get_available_cash = Mock(return_value=500_000.0)
        engine.get_daily_indicators = Mock(
            return_value={
                "rsi10": 26.48,
                "close": 978.0,
                "avg_volume": 1_000_000,
                "ema9": 990.0,
                "ema200": 950.0,
            }
        )
        engine._calculate_execution_capital = Mock(return_value=10_000.0)
        engine.get_affordable_qty = Mock(return_value=20)
        engine.parse_symbol_for_broker = Mock(return_value="STAR")
        assign_tradable_scrip_master(engine, "STAR")
        engine.has_active_buy_order = Mock(return_value=False)
        engine._attempt_place_order = Mock(return_value=(True, "ORDER_NEW"))
        engine.strategy_config = Mock()
        engine.strategy_config.user_capital = 100_000.0
        return engine


class TestPlaceReentryOrdersDayGuard:
    """Integration-style tests through place_reentry_orders."""

    def test_blocks_second_same_level_after_cycle_reset_same_day(self, reentry_engine):
        """STAR scenario: cycle 1→2 must not allow another level-30 re-entry same day."""
        today = _today_iso()
        mock_position = Mock()
        mock_position.symbol = "STAR-EQ"
        mock_position.entry_rsi = 25.0
        mock_position.closed_at = None
        mock_position.avg_price = 960.0
        mock_position.entry_price = 960.0
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 1,
                "last_rsi_above_30": _yesterday_iso() + "T09:01:21",
                "last_rsi_value": 32.0,
            },
            "reentries": [
                {
                    "level": 30,
                    "cycle": 1,
                    "qty": 10,
                    "placed_at": today,
                    "order_id": "260611000005203",
                }
            ],
        }

        updated_position = Mock()
        updated_position.symbol = mock_position.symbol
        updated_position.entry_rsi = mock_position.entry_rsi
        updated_position.closed_at = None
        updated_position.avg_price = mock_position.avg_price
        updated_position.entry_price = mock_position.entry_price
        updated_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 2,
                "last_rsi_above_30": None,
                "last_rsi_value": 26.48,
            },
            "reentries": mock_position.reentries["reentries"],
        }

        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]
        mock_positions_repo.get_by_symbol.return_value = updated_position
        mock_positions_repo.update_reentry_cycle_metadata = Mock()
        reentry_engine.positions_repo = mock_positions_repo
        reentry_engine.orders_repo = Mock()
        reentry_engine.orders_repo.list.return_value = ([], 0)

        summary = reentry_engine.place_reentry_orders()

        assert summary["attempted"] == 1
        assert summary["placed"] == 0
        assert summary.get("skipped_duplicate_level_today", 0) == 1
        reentry_engine._attempt_place_order.assert_not_called()

    def test_allows_different_level_same_day(self, reentry_engine):
        """Level 30 filled today; RSI < 20 should still allow level 20 same day."""
        today = _today_iso()
        mock_position = Mock()
        mock_position.symbol = "STAR-EQ"
        mock_position.entry_rsi = 25.0
        mock_position.closed_at = None
        mock_position.avg_price = 960.0
        mock_position.entry_price = 960.0
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [
                {
                    "level": 30,
                    "cycle": 0,
                    "qty": 10,
                    "placed_at": today,
                }
            ],
        }

        reentry_engine.get_daily_indicators = Mock(
            return_value={
                "rsi10": 18.0,
                "close": 950.0,
                "avg_volume": 1_000_000,
                "ema9": 960.0,
                "ema200": 940.0,
            }
        )

        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]
        mock_positions_repo.get_by_symbol.return_value = mock_position
        reentry_engine.positions_repo = mock_positions_repo
        reentry_engine.orders_repo = Mock()
        reentry_engine.orders_repo.list.return_value = ([], 0)

        summary = reentry_engine.place_reentry_orders()

        assert summary["attempted"] == 1
        assert summary["placed"] == 1
        reentry_engine._attempt_place_order.assert_called_once()
        call_kwargs = reentry_engine._attempt_place_order.call_args[1]
        assert call_kwargs["order_metadata"]["reentry_level"] == 20
