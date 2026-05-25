"""Regression tests: live price cache init must not break short broker tasks."""

import sys
import types
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.run_trading_service import TradingService


def _stub_src_modules():
    """Inject minimal src.* modules for TradingService.__init__ (isolated test runs)."""
    infra = sys.modules.setdefault("src.infrastructure", types.ModuleType("src.infrastructure"))
    logging_mod = types.ModuleType("src.infrastructure.logging")
    logging_mod.get_user_logger = lambda **kwargs: Mock()
    sys.modules["src.infrastructure.logging"] = logging_mod
    infra.logging = logging_mod  # type: ignore[attr-defined]

    app = sys.modules.setdefault("src.application", types.ModuleType("src.application"))
    services = sys.modules.setdefault(
        "src.application.services", types.ModuleType("src.application.services")
    )
    sched_mod = types.ModuleType("src.application.services.schedule_manager")

    class _StubScheduleManager:
        def __init__(self, db_session):
            self.db = db_session

    sched_mod.ScheduleManager = _StubScheduleManager
    sys.modules["src.application.services.schedule_manager"] = sched_mod
    services.schedule_manager = sched_mod  # type: ignore[attr-defined]
    app.services = services  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _src_stubs():
    _stub_src_modules()
    yield


@pytest.fixture
def mock_strategy_config():
    return Mock()


@pytest.fixture
def mock_db_session():
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


@patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
@patch.object(TradingService, "_subscribe_to_open_positions")
@patch.object(TradingService, "_initialize_live_prices")
@patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
@patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
@patch("modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager")
def test_initialize_skips_live_price_cache_when_disabled(  # noqa: PLR0913
    mock_session_mgr,
    mock_engine_cls,
    mock_sell_mgr_cls,
    mock_init_live,
    mock_subscribe,
    mock_prevent_conflict,
    mock_db_session,
    mock_strategy_config,
):
    """Per-task buy_orders path must not load scrip master / start LTP polling."""
    mock_prevent_conflict.return_value = True

    mock_session_mgr.return_value.get_or_create_session.return_value = Mock()

    mock_engine = mock_engine_cls.return_value
    mock_engine.login.return_value = True
    mock_engine.positions_repo = Mock()
    mock_engine.orders_repo = Mock()
    mock_engine.order_verifier = None
    mock_engine.portfolio = None

    mock_sell_mgr_cls.return_value = Mock()

    service = TradingService(
        user_id=1,
        db_session=mock_db_session,
        broker_creds={"api_key": "test"},
        strategy_config=mock_strategy_config,
        env_file="test.env",
        enable_live_price_cache=False,
    )
    assert service.initialize() is True

    mock_init_live.assert_not_called()
    assert service.price_cache is None
    assert service.scrip_master is None
    mock_subscribe.assert_not_called()


@patch("modules.kotak_neo_auto_trader.run_trading_service.prevent_service_conflict")
@patch.object(TradingService, "_subscribe_to_open_positions")
@patch.object(TradingService, "_initialize_live_prices")
@patch("modules.kotak_neo_auto_trader.run_trading_service.SellOrderManager")
@patch("modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine")
@patch("modules.kotak_neo_auto_trader.shared_session_manager.get_shared_session_manager")
def test_initialize_starts_live_price_cache_when_enabled(  # noqa: PLR0913
    mock_session_mgr,
    mock_engine_cls,
    mock_sell_mgr_cls,
    mock_init_live,
    mock_subscribe,
    mock_prevent_conflict,
    mock_db_session,
    mock_strategy_config,
):
    """Scheduler / sell_monitor path keeps Kotak LTP polling (default)."""
    mock_prevent_conflict.return_value = True

    mock_session_mgr.return_value.get_or_create_session.return_value = Mock()

    mock_engine = mock_engine_cls.return_value
    mock_engine.login.return_value = True
    mock_engine.positions_repo = Mock()
    mock_engine.orders_repo = Mock()
    mock_engine.order_verifier = None
    mock_engine.portfolio = Mock()

    mock_sell_mgr_cls.return_value = Mock()

    service_holder: list[TradingService] = []

    def _init_live():
        svc = service_holder[0]
        svc.price_cache = Mock()
        svc.scrip_master = Mock()

    mock_init_live.side_effect = _init_live

    service = TradingService(
        user_id=1,
        db_session=mock_db_session,
        broker_creds={"api_key": "test"},
        strategy_config=mock_strategy_config,
        env_file="test.env",
        enable_live_price_cache=True,
    )
    service_holder.append(service)
    assert service.initialize() is True

    mock_init_live.assert_called_once()
    mock_subscribe.assert_called_once()
    assert service.price_cache is not None
