from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.application.services.individual_service_manager import IndividualServiceManager


def test_execute_sell_monitor_sets_running_flags_for_broker_mode(db_session):
    manager = IndividualServiceManager(db_session)

    mock_service = MagicMock()
    mock_service.initialize.return_value = True
    mock_service.running = False
    mock_service.shutdown_requested = True

    def _assert_flags_when_called():
        assert mock_service.running is True
        assert mock_service.shutdown_requested is False

    mock_service.run_sell_monitor.side_effect = _assert_flags_when_called

    settings = SimpleNamespace(trade_mode=SimpleNamespace(value="broker"))

    with (
        patch(
            "src.application.services.individual_service_manager.trading_service_module.TradingService",
            return_value=mock_service,
        ),
        patch("src.application.services.individual_service_manager.get_user_logger"),
    ):
        result = manager._execute_task_logic(
            user_id=2,
            task_name="sell_monitor",
            broker_creds={"api_key": "x"},
            strategy_config=object(),
            settings=settings,
            db_session=db_session,
            config_repo=MagicMock(),
        )

    assert result == {"task": "sell_monitor", "status": "completed"}
    assert mock_service.running is False
