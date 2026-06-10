"""Unit tests for Kotak market depth parsing (9:05 log-only)."""

from modules.kotak_neo_auto_trader.utils.market_depth_utils import (
    DEPTH_DETAIL_API_FAULT,
    DEPTH_DETAIL_EMPTY_BOOK,
    DEPTH_DETAIL_QUOTE_UNAVAILABLE,
    DepthFetchStatus,
    DepthLevel,
    KOTAK_DEPTH_LEVELS,
    extract_best_ask_from_quote_row,
    extract_best_bid_from_quote_row,
    extract_buy_depth_from_quote_row,
    extract_market_depth_from_quote_payload,
    extract_sell_depth_from_quote_row,
    format_premarket_ask_depth_log,
    format_premarket_depth_log,
    unavailable_depth_snapshot,
    MarketDepthSnapshot,
)


def test_kotak_depth_level_count():
    assert KOTAK_DEPTH_LEVELS == 5


def test_extract_sell_depth_returns_five_slots():
    row = {
        "depth": {
            "sell": [
                {"price": "1259.00", "quantity": "120", "orders": "5"},
                {"price": "1260.00", "quantity": "50", "orders": "2"},
                {"price": "0.0000", "quantity": "0", "orders": "0"},
            ],
        }
    }
    levels = extract_sell_depth_from_quote_row(row)
    assert len(levels) == 5
    assert levels[0] == DepthLevel(price=1259.0, quantity=120.0, orders=5)
    assert levels[1] == DepthLevel(price=1260.0, quantity=50.0, orders=2)
    assert levels[2] is None


def test_extract_buy_depth_returns_five_slots():
    row = {
        "depth": {
            "buy": [
                {"price": "1258.80", "quantity": "38", "orders": "3"},
                {"price": "1258.70", "quantity": "100", "orders": "4"},
            ],
        }
    }
    levels = extract_buy_depth_from_quote_row(row)
    assert levels[0] == DepthLevel(price=1258.8, quantity=38.0, orders=3)
    assert levels[1] == DepthLevel(price=1258.7, quantity=100.0, orders=4)
    assert levels[4] is None


def test_extract_best_bid_and_ask():
    row = {
        "depth": {
            "buy": [{"price": "0", "quantity": "0", "orders": "0"}, {"price": "100", "quantity": "1", "orders": "1"}],
            "sell": [{"price": "101", "quantity": "2", "orders": "1"}],
        }
    }
    assert extract_best_bid_from_quote_row(row) == DepthLevel(100.0, 1.0, 1)
    assert extract_best_ask_from_quote_row(row) == DepthLevel(101.0, 2.0, 1)


def test_extract_market_depth_from_list_payload_ok():
    payload = [
        {"fault": {"code": "400"}},
        {
            "depth": {
                "buy": [{"price": "99.5", "quantity": "10", "orders": "1"}],
                "sell": [{"price": "101.5", "quantity": "10", "orders": "1"}],
            }
        },
    ]
    snapshot = extract_market_depth_from_quote_payload(payload)
    assert snapshot.status == DepthFetchStatus.OK
    assert snapshot.bid_levels[0].price == 99.5
    assert snapshot.ask_levels[0].price == 101.5


def test_extract_market_depth_api_fault():
    snapshot = extract_market_depth_from_quote_payload(
        {"fault": {"code": "400", "message": "Invalid type"}}
    )
    assert snapshot.status == DepthFetchStatus.UNAVAILABLE
    assert snapshot.status_detail == DEPTH_DETAIL_API_FAULT


def test_extract_market_depth_quote_unavailable():
    snapshot = extract_market_depth_from_quote_payload(None)
    assert snapshot.status == DepthFetchStatus.UNAVAILABLE
    assert snapshot.status_detail == DEPTH_DETAIL_QUOTE_UNAVAILABLE


def test_extract_market_depth_empty_book():
    row = {
        "depth": {
            "buy": [{"price": "0", "quantity": "0", "orders": "0"}],
            "sell": [{"price": "0", "quantity": "0", "orders": "0"}],
        }
    }
    snapshot = extract_market_depth_from_quote_payload([row])
    assert snapshot.status == DepthFetchStatus.EMPTY
    assert snapshot.status_detail == DEPTH_DETAIL_EMPTY_BOOK


def test_format_premarket_depth_log_ok():
    snapshot = MarketDepthSnapshot(
        bid_levels=(
            DepthLevel(price=1258.8, quantity=38.0, orders=3),
            None,
            None,
            None,
            None,
        ),
        ask_levels=(
            DepthLevel(price=1259.0, quantity=120.0, orders=3),
            DepthLevel(price=1260.0, quantity=50.0, orders=2),
            None,
            None,
            None,
        ),
        status=DepthFetchStatus.OK,
        status_detail="",
    )
    msg = format_premarket_depth_log(
        "RELIANCE",
        ltp=1258.8,
        snapshot=snapshot,
        entry_type="reentry",
    )
    assert "pre-market depth [ok]" in msg
    assert "bids (5 levels, 1 live)" in msg
    assert "asks (5 levels, 2 live)" in msg
    assert "LTP Rs 1258.80" in msg


def test_format_premarket_depth_log_empty():
    snapshot = unavailable_depth_snapshot(DEPTH_DETAIL_EMPTY_BOOK)
    snapshot = MarketDepthSnapshot(
        bid_levels=snapshot.bid_levels,
        ask_levels=snapshot.ask_levels,
        status=DepthFetchStatus.EMPTY,
        status_detail=DEPTH_DETAIL_EMPTY_BOOK,
    )
    msg = format_premarket_depth_log("TCS", ltp=3500.0, snapshot=snapshot)
    assert "pre-market depth [empty]" in msg
    assert DEPTH_DETAIL_EMPTY_BOOK in msg
    assert "LTP Rs 3500.00" in msg


def test_format_premarket_depth_log_unavailable():
    snapshot = unavailable_depth_snapshot(DEPTH_DETAIL_API_FAULT)
    msg = format_premarket_depth_log("INFY", ltp=1500.0, snapshot=snapshot)
    assert "pre-market depth [unavailable]" in msg
    assert DEPTH_DETAIL_API_FAULT in msg


def test_format_premarket_ask_depth_log_no_liquidity():
    msg = format_premarket_ask_depth_log(
        "TCS",
        ltp=3500.0,
        ask_levels=tuple(None for _ in range(5)),
        entry_type="initial",
    )
    assert "pre-market depth [empty]" in msg
    assert DEPTH_DETAIL_EMPTY_BOOK in msg
