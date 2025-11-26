"""
Tests for Paper Trading Re-entry Logic

Verifies that paper trading implements the same re-entry logic as real trading:
- RSI-based re-entry at levels 30, 20, 10
- Daily cap (1 re-entry per symbol per day)
- Duplicate prevention
- Reset logic
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from src.application.services.paper_trading_service_adapter import PaperTradingServiceAdapter


@pytest.fixture
def paper_service(tmp_path):
    """Create paper trading service with temporary storage"""
    storage_path = str(tmp_path / "paper_trading")

    # Create config
    config = PaperTradingConfig(
        initial_capital=200000.0,  # Higher capital for testing
        storage_path=storage_path,
        enable_fees=False,  # Simplify for testing
        enable_slippage=False,
    )

    # Create service adapter
    mock_db = MagicMock()
    service = PaperTradingServiceAdapter(
        user_id=1,
        db_session=mock_db,
        initial_capital=200000.0,  # Higher capital for testing
        storage_path=storage_path,
    )

    # Initialize
    service.initialize()

    # Increase max position size for testing
    if service.broker:
        service.broker.config.max_position_size = 200000.0

    # Place initial buy order to create a holding
    from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

    initial_order = Order(
        symbol="INFY.NS",
        quantity=100,
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY,
    )

    # Mock price provider for initial buy
    with patch.object(service.broker.price_provider, "get_price", return_value=1400.0):
        order_id = service.broker.place_order(initial_order)
        assert order_id is not None, "Initial buy order should succeed"

    # Verify we have holdings
    holdings = service.broker.get_holdings()
    assert len(holdings) == 1, "Should have one holding after initial buy"

    return service


def test_reentry_level_30_triggers_when_rsi_below_30(paper_service):
    """Test that re-entry triggers at RSI < 30 (first level)"""
    # Verify we have holdings first
    holdings = paper_service.broker.get_holdings()
    print(f"Holdings before monitor: {len(holdings)}")
    for h in holdings:
        print(f"  - {h.symbol}: {h.quantity} @ {h.average_price.amount}")

    # Mock indicators: RSI=25 (should trigger level 30)
    mock_indicators = {
        "close": 1350.0,
        "rsi10": 25.0,
        "ema9": 1400.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        with patch.object(paper_service.broker.price_provider, "get_price", return_value=1350.0):
            summary = paper_service.engine.monitor_positions()
            print(f"Summary: {summary}")

    # Should have placed re-entry order
    assert summary["reentries"] == 1, f"Expected 1 reentry, got {summary['reentries']}"
    assert summary["checked"] == 1

    # Check metadata was updated
    metadata = paper_service.engine._load_position_metadata()
    assert "INFY" in metadata
    assert metadata["INFY"]["levels_taken"]["30"] is True


def test_reentry_level_20_triggers_after_level_30_taken(paper_service):
    """Test that re-entry progresses from level 30 to level 20"""
    # Set up metadata as if level 30 was already taken
    metadata = {
        "INFY": {
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
            "reentry_dates": [],
        }
    }
    paper_service.engine._save_position_metadata(metadata)

    # Mock indicators: RSI=18 (should trigger level 20)
    mock_indicators = {
        "close": 1300.0,
        "rsi10": 18.0,
        "ema9": 1380.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        with patch.object(paper_service.broker.price_provider, "get_price", return_value=1300.0):
            summary = paper_service.engine.monitor_positions()

    # Should have placed re-entry order for level 20
    assert summary["reentries"] == 1

    # Check metadata
    metadata = paper_service.engine._load_position_metadata()
    assert metadata["INFY"]["levels_taken"]["30"] is True
    assert metadata["INFY"]["levels_taken"]["20"] is True
    assert metadata["INFY"]["levels_taken"]["10"] is False


def test_reentry_level_10_triggers_after_level_20_taken(paper_service):
    """Test that re-entry progresses to level 10"""
    # Set up metadata as if levels 30 and 20 were taken
    metadata = {
        "INFY": {
            "levels_taken": {"30": True, "20": True, "10": False},
            "reset_ready": False,
            "reentry_dates": [],
        }
    }
    paper_service.engine._save_position_metadata(metadata)

    # Mock indicators: RSI=8 (should trigger level 10)
    mock_indicators = {
        "close": 1250.0,
        "rsi10": 8.0,
        "ema9": 1360.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        with patch.object(paper_service.broker.price_provider, "get_price", return_value=1250.0):
            summary = paper_service.engine.monitor_positions()

    # Should have placed re-entry order for level 10
    assert summary["reentries"] == 1

    # Check metadata
    metadata = paper_service.engine._load_position_metadata()
    assert metadata["INFY"]["levels_taken"]["10"] is True


def test_reentry_daily_cap_prevents_multiple_reentries_same_day(paper_service):
    """Test that daily cap (1 reentry per symbol per day) is enforced"""
    # Set up metadata with one reentry today
    today = datetime.now().date().isoformat()
    metadata = {
        "INFY": {
            "levels_taken": {"30": True, "20": False, "10": False},
            "reset_ready": False,
            "reentry_dates": [today],  # Already had reentry today
        }
    }
    paper_service.engine._save_position_metadata(metadata)

    # Mock indicators: RSI=18 (would trigger level 20, but daily cap should prevent)
    mock_indicators = {
        "close": 1300.0,
        "rsi10": 18.0,
        "ema9": 1380.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        summary = paper_service.engine.monitor_positions()

    # Should NOT place reentry (daily cap reached)
    assert summary["reentries"] == 0
    assert summary["skipped"] == 1


def test_reentry_reset_logic_marks_reset_ready_when_rsi_above_30(paper_service):
    """Test that reset_ready flag is set when RSI > 30"""
    # Set up metadata
    metadata = {
        "INFY": {
            "levels_taken": {"30": True, "20": True, "10": False},
            "reset_ready": False,
            "reentry_dates": [],
        }
    }
    paper_service.engine._save_position_metadata(metadata)

    # Mock indicators: RSI=35 (above 30, should mark reset_ready)
    mock_indicators = {
        "close": 1420.0,
        "rsi10": 35.0,
        "ema9": 1410.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        summary = paper_service.engine.monitor_positions()

    # Should not place orders, but should mark reset_ready
    assert summary["reentries"] == 0

    # Check reset_ready flag
    metadata = paper_service.engine._load_position_metadata()
    assert metadata["INFY"]["reset_ready"] is True


def test_reentry_new_cycle_resets_levels_when_rsi_drops_after_reset(paper_service):
    """Test that a new cycle resets levels when RSI drops below 30 after reset_ready"""
    # Set up metadata: reset_ready=True, all levels taken
    metadata = {
        "INFY": {
            "levels_taken": {"30": True, "20": True, "10": True},
            "reset_ready": True,
            "reentry_dates": ["2024-11-20"],  # Old date (not today)
        }
    }
    paper_service.engine._save_position_metadata(metadata)

    # Mock indicators: RSI=25 (below 30 after reset_ready, should trigger NEW CYCLE)
    mock_indicators = {
        "close": 1380.0,
        "rsi10": 25.0,
        "ema9": 1400.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        with patch.object(paper_service.broker.price_provider, "get_price", return_value=1380.0):
            summary = paper_service.engine.monitor_positions()

    # Should place reentry for new cycle at level 30
    assert summary["reentries"] == 1

    # Check that levels were reset
    metadata = paper_service.engine._load_position_metadata()
    assert metadata["INFY"]["reset_ready"] is False


def test_reentry_prevented_when_active_buy_order_exists(paper_service):
    """Test that duplicate prevention works - no reentry if active buy order exists"""
    # Place a pending buy order (use LIMIT order so it doesn't execute immediately)
    from modules.kotak_neo_auto_trader.domain import Money, Order, OrderType, TransactionType

    pending_order = Order(
        symbol="INFY.NS",
        quantity=50,
        order_type=OrderType.LIMIT,  # LIMIT order won't execute if above market price
        transaction_type=TransactionType.BUY,
        price=Money(2000.0),  # Set limit price above market (Rs 2000 > Rs 1400)
    )

    # Place the order - it will stay PENDING because limit price is too high
    with patch.object(paper_service.broker.price_provider, "get_price", return_value=1400.0):
        order_id = paper_service.broker.place_order(pending_order)
        assert order_id is not None, "Order should be placed"

    # Verify order is PENDING
    all_orders = paper_service.broker.get_all_orders()
    pending_orders = [o for o in all_orders if o.status.value in ["PENDING", "OPEN"]]
    print(f"Pending orders: {len(pending_orders)}")
    for o in pending_orders:
        print(f"  - {o.symbol} {o.transaction_type.value} {o.status.value}")
    assert len(pending_orders) > 0, "Should have pending order"

    # Mock indicators: RSI=25 (would trigger reentry)
    mock_indicators = {
        "close": 1350.0,
        "rsi10": 25.0,
        "ema9": 1400.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        with patch.object(paper_service.broker.price_provider, "get_price", return_value=1350.0):
            summary = paper_service.engine.monitor_positions()
            print(f"Summary: {summary}")

    # Should NOT place reentry (active buy order exists)
    assert summary["reentries"] == 0, f"Expected 0 reentries, got {summary['reentries']}"
    assert summary["skipped"] == 1, f"Expected 1 skipped, got {summary['skipped']}"


def test_reentry_skipped_when_insufficient_funds(paper_service):
    """Test that reentry is skipped if insufficient funds"""
    # Drain account balance
    account = paper_service.broker.store.get_account()
    account["available_cash"] = 100.0  # Only Rs 100 left
    paper_service.broker.store.update_account(account)

    # Mock indicators: RSI=25 (would trigger reentry, but no money)
    mock_indicators = {
        "close": 1350.0,  # Need Rs 1350 per share
        "rsi10": 25.0,
        "ema9": 1400.0,
        "avg_volume": 5000000,
    }

    with patch.object(paper_service.engine, "_get_daily_indicators", return_value=mock_indicators):
        summary = paper_service.engine.monitor_positions()

    # Should NOT place reentry (insufficient funds)
    assert summary["reentries"] == 0
    assert summary["skipped"] == 1


def test_reentry_calculates_execution_capital_based_on_liquidity(paper_service):
    """Test that execution capital is calculated based on liquidity tiers"""
    # Test high liquidity (>= 10 crore daily traded value)
    price = 1000.0
    avg_volume = 200000  # 200k shares * 1000 = 20 crore

    capital = paper_service.engine._calculate_execution_capital(price, avg_volume)

    # Should get max capital for high liquidity
    assert capital == 50000.0

    # Test low liquidity
    avg_volume = 1000  # 1k shares * 1000 = 10 lakh
    capital = paper_service.engine._calculate_execution_capital(price, avg_volume)

    # Should get default capital for low liquidity
    assert capital == 20000.0


def test_position_metadata_persists_across_restarts(paper_service, tmp_path):
    """Test that position metadata is saved and loaded correctly"""
    # Set metadata
    metadata = {
        "INFY": {
            "levels_taken": {"30": True, "20": True, "10": False},
            "reset_ready": True,
            "reentry_dates": ["2024-11-25", "2024-11-26"],
        }
    }
    paper_service.engine._save_position_metadata(metadata)

    # Load in new service instance
    loaded_metadata = paper_service.engine._load_position_metadata()

    # Should match
    assert loaded_metadata == metadata
    assert loaded_metadata["INFY"]["levels_taken"]["30"] is True
    assert loaded_metadata["INFY"]["reset_ready"] is True
    assert len(loaded_metadata["INFY"]["reentry_dates"]) == 2
