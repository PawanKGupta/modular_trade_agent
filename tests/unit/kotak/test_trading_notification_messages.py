"""Unit tests for compact trading notification message templates."""

from modules.kotak_neo_auto_trader.utils.market_depth_utils import (
    DepthFetchStatus,
    DepthLevel,
    MarketDepthSnapshot,
)
from modules.kotak_neo_auto_trader.utils.trading_notification_messages import (
    format_premarket_adjusted_telegram,
    format_premarket_ema9_cancel_telegram,
    format_premarket_task_in_app_summary,
    strip_markdown_for_plain,
)


def test_format_premarket_adjusted_telegram_with_depth():
    depth = MarketDepthSnapshot(
        status=DepthFetchStatus.OK,
        bid_levels=[DepthLevel(price=104.8, quantity=38, orders=1)],
        ask_levels=[DepthLevel(price=105.2, quantity=120, orders=2)],
    )
    message = format_premarket_adjusted_telegram(
        symbol="RELIANCE",
        entry_type="reentry",
        original_qty=2000,
        new_qty=1904,
        premarket_ltp=105.0,
        gap_pct=5.0,
        market_depth=depth,
    )
    assert "*9:05 Pre-market*" in message
    assert "`RELIANCE`" in message
    assert "qty 2000→1904 MARKET" in message
    assert "Ask ₹105.20×120" in message
    assert "Bid ₹104.80×38" in message


def test_format_premarket_ema9_cancel_telegram():
    message = format_premarket_ema9_cancel_telegram(
        symbol="TCS",
        entry_type="buy",
        premarket_ltp=4100.0,
        ema9=4000.0,
        ema9_threshold=3960.0,
    )
    assert "*9:05 Cancelled*" in message
    assert "`TCS`" in message
    assert "EMA9" in message


def test_strip_markdown_for_plain():
    assert strip_markdown_for_plain("*9:05* · `RELIANCE`") == "9:05 · RELIANCE"


def test_format_premarket_task_in_app_summary():
    assert (
        format_premarket_task_in_app_summary({"adjusted": 3, "cancelled_above_ema9": 1})
        == "9:05 pre-market: 3 adjusted, 1 cancelled (EMA9)."
    )
    assert format_premarket_task_in_app_summary({}) == "9:05 pre-market: no order changes."
