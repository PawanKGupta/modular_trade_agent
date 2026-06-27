"""
Direct unit tests for the decomposed CapitalSizingService, OrderPlacementService,
and PositionMonitorService.
"""

from unittest.mock import Mock

from modules.kotak_neo_auto_trader.services.capital_sizing_service import CapitalSizingService
from modules.kotak_neo_auto_trader.services.order_placement_service import OrderPlacementService
from modules.kotak_neo_auto_trader.services.position_monitor_service import PositionMonitorService

try:
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
except ImportError:

    class DbOrderStatus:
        PENDING = "PENDING"
        ONGOING = "ONGOING"
        CLOSED = "CLOSED"


# ==============================================================================
# CapitalSizingService Tests
# ==============================================================================


def test_get_affordable_qty():
    service = CapitalSizingService()
    # No portfolio -> 0
    assert service.get_affordable_qty(100.0) == 0

    # Mock portfolio and cash limit
    mock_portfolio = Mock()
    mock_portfolio.get_limits.return_value = {"availMargin": "1000.0"}
    service.portfolio = mock_portfolio

    # 1000 / 100 = 10
    assert service.get_affordable_qty(100.0) == 10
    # 1000 / 150 = 6
    assert service.get_affordable_qty(150.0) == 6


def test_extract_available_cash_from_limits():
    service = CapitalSizingService()

    # Case A: Cash key as float
    val, key = service._extract_available_cash_from_limits({"availMargin": 5000.0})
    assert val == 5000.0

    # Case B: Cash key as string with "Rs" and commas
    val, key = service._extract_available_cash_from_limits({"availMargin": "Rs 10,250.50"})
    assert val == 10250.50

    # Case C: Alternate keys (e.g., cash, margin, etc.)
    val, key = service._extract_available_cash_from_limits({"cash": "1000"})
    assert val == 1000.0
    val, key = service._extract_available_cash_from_limits({"marginAvailable": "2000"})
    assert val == 2000.0

    # Case D: Missing / invalid cash -> fallback
    val, key = service._extract_available_cash_from_limits({})
    assert val == 0.0
    val, key = service._extract_available_cash_from_limits({"availMargin": "InvalidNumber"})
    assert val == 0.0


def test_check_order_margin_failure_path():
    service = CapitalSizingService()

    mock_rest = Mock()
    mock_rest.check_margin.return_value = {
        "stat": "Not_Ok",
        "insufFund": "500.0",
        "reqMargin": "1500.0",
        "avlCash": "1000.0",
    }

    mock_auth = Mock()
    mock_auth.get_rest_client.return_value = mock_rest
    service.auth = mock_auth

    service.portfolio = Mock()
    service.portfolio.get_limits.return_value = {"availMargin": 1000.0}

    # Should return (False, avl_cash, req_margin, shortfall, False)
    mock_scrip_master = Mock()
    mock_scrip_master.get_token.return_value = "12345"
    service.scrip_master = mock_scrip_master

    # Setup mock orders api
    service.portfolio.orders = mock_rest

    has_suff, avl, req, shortfall, ok = service.check_order_margin(
        symbol="RELIANCE-EQ", price=100.0, qty=10, transaction_type="B", product="CNC"
    )
    assert has_suff is False
    assert avl == 1000.0
    assert req == 1500.0
    assert shortfall == 500.0
    assert ok is False


def test_check_order_margin_payload_structures():
    service = CapitalSizingService()

    mock_rest = Mock()
    mock_auth = Mock()
    mock_auth.get_rest_client.return_value = mock_rest
    service.auth = mock_auth

    service.portfolio = Mock()
    service.portfolio.get_limits.return_value = {"availMargin": 10000.0}

    mock_scrip_master = Mock()
    mock_scrip_master.get_token.return_value = "12345"
    service.scrip_master = mock_scrip_master

    # Structure 1: Flat payload
    mock_rest.check_margin.return_value = {
        "stat": "Ok",
        "stcode": "200",
        "reqMargin": "3000.0",
        "avlCash": "10000.0",
    }
    has_suff, avl, req, shortfall, ok = service.check_order_margin("XYZ-EQ", 100.0, 10)
    assert has_suff is True
    assert avl == 10000.0
    assert req == 3000.0
    assert shortfall == 0.0
    assert ok is True

    # Structure 2: Data-wrapped dictionary payload
    mock_rest.check_margin.return_value = {
        "stat": "Ok",
        "stcode": "200",
        "data": {
            "reqMargin": "4000.0",
            "avlCash": "10000.0",
        },
    }
    has_suff, avl, req, shortfall, ok = service.check_order_margin("XYZ-EQ", 100.0, 10)
    assert req == 4000.0

    # Structure 3: Data-wrapped list payload (data[0])
    mock_rest.check_margin.return_value = {
        "stat": "Ok",
        "stcode": "200",
        "data": [
            {
                "reqMargin": "5000.0",
                "avlCash": "10000.0",
            }
        ],
    }
    has_suff, avl, req, shortfall, ok = service.check_order_margin("XYZ-EQ", 100.0, 10)
    assert req == 5000.0


# ==============================================================================
# OrderPlacementService Tests
# ==============================================================================


def test_has_active_buy_order_broker_hit():
    service = OrderPlacementService()

    # Case A: Broker pending orders has matching symbol
    mock_orders = Mock()
    mock_orders.get_pending_orders.return_value = [
        {"transactionType": "B", "tradingSymbol": "RELIANCE-EQ"},
        {"transactionType": "S", "tradingSymbol": "INFY-EQ"},
    ]
    service.orders = mock_orders

    assert service.has_active_buy_order("RELIANCE") is True
    assert service.has_active_buy_order("INFY") is False


def test_has_active_buy_order_db_fallback():
    service = OrderPlacementService()

    # Mock broker to fail, triggering DB fallback
    mock_orders = Mock()
    mock_orders.get_pending_orders.side_effect = RuntimeError("Broker down")
    service.orders = mock_orders

    # Mock DB repo
    mock_repo = Mock()
    service.orders_repo = mock_repo
    service.user_id = 42

    # DB order stub
    class StubDbOrder:
        def __init__(self, symbol, side, status, execution_qty=None):
            self.symbol = symbol
            self.side = side
            self.status = status
            self.execution_qty = execution_qty
            self.id = 123

    # Case A: DB has unfilled buy order -> block (returns True)
    mock_repo.list.return_value = (
        [StubDbOrder("RELIANCE-EQ", "buy", DbOrderStatus.PENDING, execution_qty=None)],
        None,
    )
    assert service.has_active_buy_order("RELIANCE") is True

    # Case B: DB has filled buy order -> don't block (returns False)
    mock_repo.list.return_value = (
        [StubDbOrder("RELIANCE-EQ", "buy", DbOrderStatus.CLOSED, execution_qty=10)],
        None,
    )
    assert service.has_active_buy_order("RELIANCE") is False


def test_get_order_variety_for_market_hours(monkeypatch):
    import core.volume_analysis

    service = OrderPlacementService()

    # Case A: Market hours -> REGULAR
    monkeypatch.setattr(core.volume_analysis, "is_market_hours", lambda: True)
    assert service.get_order_variety_for_market_hours() == "REGULAR"

    # Case B: After market hours -> default
    monkeypatch.setattr(core.volume_analysis, "is_market_hours", lambda: False)
    service.strategy_config = Mock()
    service.strategy_config.default_variety = "AMO"
    assert service.get_order_variety_for_market_hours() == "AMO"


def test_check_for_manual_orders():
    service = OrderPlacementService()
    service.user_id = 42

    # Mock orders repo
    mock_repo = Mock()
    service.orders_repo = mock_repo
    service.orders = Mock()  # mock check to enable the method

    # Setup pending orders list
    pending = [
        {
            "tradingSymbol": "RELIANCE-EQ",
            "transactionType": "B",
            "qty": "10",
            "price": "2500.0",
            "nOrdNo": "888",
        },
        {
            "tradingSymbol": "INFY-EQ",
            "transactionType": "B",
            "qty": "5",
            "price": "1400.0",
            "nOrdNo": "999",
        },
        {
            "tradingSymbol": "TCS-EQ",
            "transactionType": "S",
            "qty": "2",
            "price": "3000.0",
            "nOrdNo": "777",
        },
    ]

    # Setup repo to recognise RELIANCE as system order, INFY as manual order
    mock_repo.get_by_broker_order_id.side_effect = lambda uid, oid: (
        "RELIANCE_DB_ORDER" if oid == "888" else None
    )

    res = service.check_for_manual_orders(symbol="RELIANCE", cached_pending_orders=pending)

    assert res["has_system_order"] is True
    assert len(res["system_orders"]) == 1
    assert res["system_orders"][0]["order_id"] == "888"

    res2 = service.check_for_manual_orders(symbol="INFY", cached_pending_orders=pending)
    assert res2["has_manual_order"] is True
    assert len(res2["manual_orders"]) == 1
    assert res2["manual_orders"][0]["order_id"] == "999"


# ==============================================================================
# PositionMonitorService Tests
# ==============================================================================


def test_determine_reentry_level_progression():
    service = PositionMonitorService()

    # Stub position
    class StubPosition:
        def __init__(self, reentries=None, entry_rsi=25.0):
            self.reentries = reentries
            self.entry_rsi = entry_rsi

    # Case A: Entry RSI is 25 (level 30 taken by default). Current RSI is 15.
    # Level 20 should be available.
    pos = StubPosition(entry_rsi=25.0)
    level, updates = service.determine_reentry_level(entry_rsi=25.0, current_rsi=15.0, position=pos)
    assert level == 20
    assert updates["current_cycle"] is None  # no cycle change yet

    # Case B: Skipper. Current RSI drops directly to 8 (skipping 20).
    # Should trigger level 10.
    level, updates = service.determine_reentry_level(entry_rsi=25.0, current_rsi=8.0, position=pos)
    assert level == 10


def test_determine_reentry_level_cycle_metadata_formats():
    service = PositionMonitorService()

    class StubPosition:
        def __init__(self, reentries):
            self.reentries = reentries
            self.entry_rsi = 25.0

    # Dict format of reentries cycle metadata
    pos_dict = StubPosition(
        reentries={"current_cycle": 1, "reentries": [{"cycle": 1, "level": 20}]}
    )
    level, updates = service.determine_reentry_level(
        entry_rsi=25.0, current_rsi=5.0, position=pos_dict
    )
    # Since level 20 is taken in cycle 1, level 10 should be the next level
    assert level == 10

    # List format of reentries cycle metadata (backward compatibility)
    pos_list = StubPosition(reentries=[{"level": 20}])
    level, updates = service.determine_reentry_level(
        entry_rsi=25.0, current_rsi=5.0, position=pos_list
    )
    assert level == 10


def test_determine_reentry_level_reset_detection():
    service = PositionMonitorService()

    class StubPosition:
        def __init__(self, reentries):
            self.reentries = reentries
            self.entry_rsi = 25.0

    # RSI goes above 30 -> stores reset flag
    pos = StubPosition(
        reentries={"_cycle_metadata": {"current_cycle": 0, "last_rsi_above_30": None}}
    )
    level, updates = service.determine_reentry_level(entry_rsi=25.0, current_rsi=35.0, position=pos)
    assert updates["last_rsi_above_30"] is not None

    # RSI drops below 30 after last_rsi_above_30 exists -> reset triggers (cycle increments)
    pos_reset = StubPosition(
        reentries={
            "_cycle_metadata": {"current_cycle": 0, "last_rsi_above_30": "2026-06-11T09:00:00"}
        }
    )
    level, updates = service.determine_reentry_level(
        entry_rsi=25.0, current_rsi=18.0, position=pos_reset
    )
    assert updates["current_cycle"] == 1
    assert updates["last_rsi_above_30"] is None  # cleared reset flag
    assert level == 20  # reset triggered level 20 because current RSI is 18
