#!/usr/bin/env python3
"""
Tests for run_individual_service.py script.

Tests cover:
1. Argument parsing (--user-id, --task)
2. Service loop execution for continuous services (sell_monitor)
3. One-time task execution (premarket_retry, analysis, buy_orders, eod_cleanup)
4. Service lifecycle management (marking as running/stopped)
5. Error handling
6. Database session management
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class TestRunIndividualServiceArgumentParsing:
    """Test argument parsing for run_individual_service.py"""

    def test_parse_arguments_with_valid_input(self):
        """Test that valid arguments are parsed correctly"""
        from scripts.run_individual_service import main  # noqa: PLC0415

        with (
            patch("scripts.run_individual_service.run_service_loop"),
            patch("scripts.run_individual_service.get_session") as mock_get_session,
        ):
            mock_db = MagicMock()
            mock_get_session.return_value = iter([mock_db])

            # Mock sys.argv
            test_args = ["run_individual_service.py", "--user-id", "1", "--task", "sell_monitor"]
            with patch.object(sys, "argv", test_args):
                with patch("scripts.run_individual_service.get_user_logger"):
                    try:
                        main()
                    except SystemExit:
                        pass  # argparse may call sys.exit

            # Verify get_session was called
            mock_get_session.assert_called_once()

    def test_parse_arguments_missing_user_id(self):
        """Test that missing --user-id raises error"""
        from scripts.run_individual_service import main  # noqa: PLC0415

        test_args = ["run_individual_service.py", "--task", "sell_monitor"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):  # argparse calls sys.exit on error
                main()

    def test_parse_arguments_missing_task(self):
        """Test that missing --task raises error"""
        from scripts.run_individual_service import main  # noqa: PLC0415

        test_args = ["run_individual_service.py", "--user-id", "1"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):  # argparse calls sys.exit on error
                main()


class TestRunIndividualServiceLoop:
    """Test service loop execution"""

    def test_run_service_loop_continuous_service(self):
        """Test that continuous services (sell_monitor) run in a loop"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "sell_monitor"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status = MagicMock()
        mock_status.status = "running"  # Service is running
        mock_status_repo.get_status.return_value = mock_status
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo
        mock_service_manager.run_once = MagicMock(
            side_effect=[
                (True, "Success", {}),
                (True, "Success", {}),
                (True, "Success", {}),
            ]
        )

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
            patch("time.sleep") as mock_sleep,  # Mock sleep to speed up test
        ):
            # Set status to stopped after 2 iterations to exit loop
            call_count = 0

            def get_status_side_effect(*args):
                nonlocal call_count
                call_count += 1
                if call_count >= 3:  # Stop after 2 iterations
                    mock_status.status = "stopped"
                return mock_status

            mock_status_repo.get_status.side_effect = get_status_side_effect

            run_service_loop(user_id, task_name, db_session)

            # Verify service was marked as running
            mock_status_repo.mark_running.assert_called_once_with(user_id, task_name)

            # Verify run_once was called (at least once for continuous service)
            assert mock_service_manager.run_once.call_count >= 1

            # Verify sleep was called (for continuous service)
            assert mock_sleep.call_count >= 1

            # Verify service was marked as stopped
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)

    def test_run_service_loop_one_time_task(self):
        """Test that one-time tasks execute once and exit"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "premarket_retry"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo
        mock_service_manager.run_once = MagicMock(return_value=(True, "Success", {}))

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
            patch("time.sleep"),  # Mock sleep
        ):
            run_service_loop(user_id, task_name, db_session)

            # Verify service was marked as running
            mock_status_repo.mark_running.assert_called_once_with(user_id, task_name)

            # Verify run_once was called once
            assert mock_service_manager.run_once.call_count == 1

            # Verify service was marked as stopped
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)

    def test_run_service_loop_handles_stop_signal(self):
        """Test that service loop exits when status is stopped"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "sell_monitor"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status = MagicMock()
        mock_status.status = "stopped"  # Service is stopped
        mock_status_repo.get_status.return_value = mock_status
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
        ):
            run_service_loop(user_id, task_name, db_session)

            # Verify service was marked as running
            mock_status_repo.mark_running.assert_called_once_with(user_id, task_name)

            # Verify run_once was NOT called (service stopped immediately)
            assert mock_service_manager.run_once.call_count == 0

            # Verify service was marked as stopped
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)

    def test_run_service_loop_handles_keyboard_interrupt(self):
        """Test that KeyboardInterrupt is handled gracefully"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "sell_monitor"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status = MagicMock()
        mock_status.status = "running"
        mock_status_repo.get_status.return_value = mock_status
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo
        mock_service_manager.run_once = MagicMock(side_effect=KeyboardInterrupt())

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
        ):
            run_service_loop(user_id, task_name, db_session)

            # Verify service was marked as stopped even after interrupt
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)

    def test_run_service_loop_handles_task_execution_error(self):
        """Test that task execution errors are handled gracefully"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "premarket_retry"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo
        mock_service_manager.run_once = MagicMock(side_effect=Exception("Task failed"))

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
            patch("time.sleep"),  # Mock sleep
        ):
            run_service_loop(user_id, task_name, db_session)

            # Verify service was marked as stopped even after error
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)

    def test_run_service_loop_handles_unknown_task(self):
        """Test that unknown tasks exit gracefully"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "unknown_task"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
        ):
            run_service_loop(user_id, task_name, db_session)

            # Verify service was marked as stopped
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)

    def test_run_service_loop_continuous_service_continues_on_failure(self):
        """Test that continuous services continue running even on task failure"""
        from scripts.run_individual_service import run_service_loop  # noqa: PLC0415

        user_id = 1
        task_name = "sell_monitor"
        db_session = MagicMock()

        mock_service_manager = MagicMock()
        mock_status_repo = MagicMock()
        mock_status_repo.mark_running = MagicMock()
        mock_status_repo.mark_stopped = MagicMock()
        mock_service_manager._status_repo = mock_status_repo

        # Track iterations to control when to stop
        iteration_count = 0

        def get_status_side_effect(*args):
            """Return running status for first 2 iterations, then stopped"""
            nonlocal iteration_count
            iteration_count += 1
            mock_status = MagicMock()
            if iteration_count <= 2:
                mock_status.status = "running"
            else:
                mock_status.status = "stopped"
            return mock_status

        mock_status_repo.get_status.side_effect = get_status_side_effect

        # First call fails, second succeeds
        run_once_call_count = 0

        def run_once_side_effect(*args):
            nonlocal run_once_call_count
            run_once_call_count += 1
            if run_once_call_count == 1:
                return (False, "Task failed", {})
            else:
                return (True, "Success", {})

        mock_service_manager.run_once = MagicMock(side_effect=run_once_side_effect)

        with (
            patch(
                "scripts.run_individual_service.IndividualServiceManager",
                return_value=mock_service_manager,
            ),
            patch("scripts.run_individual_service.get_user_logger"),
            patch("time.sleep"),  # Mock sleep to prevent actual waiting
        ):
            run_service_loop(user_id, task_name, db_session)

            # Verify run_once was called multiple times (continued after failure)
            assert mock_service_manager.run_once.call_count >= 2

            # Verify service was marked as stopped
            mock_status_repo.mark_stopped.assert_called_once_with(user_id, task_name)


class TestRunIndividualServiceMain:
    """Test main() function"""

    def test_main_calls_run_service_loop(self):
        """Test that main() calls run_service_loop with correct arguments"""
        from scripts.run_individual_service import main  # noqa: PLC0415

        with (
            patch("scripts.run_individual_service.run_service_loop"),
            patch("scripts.run_individual_service.get_session") as mock_get_session,
            patch("scripts.run_individual_service.get_user_logger"),
        ):
            mock_db = MagicMock()
            mock_get_session.return_value = iter([mock_db])

            test_args = ["run_individual_service.py", "--user-id", "42", "--task", "analysis"]
            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit:
                    pass  # argparse may call sys.exit

            # Verify get_session was called
            mock_get_session.assert_called_once()

    def test_main_handles_exceptions(self):
        """Test that main() handles exceptions gracefully"""
        from scripts.run_individual_service import main  # noqa: PLC0415

        with (
            patch(
                "scripts.run_individual_service.run_service_loop",
                side_effect=Exception("Error"),
            ),
            patch("scripts.run_individual_service.get_session") as mock_get_session,
            patch("scripts.run_individual_service.get_user_logger") as mock_logger,
        ):
            mock_db = MagicMock()
            mock_get_session.return_value = iter([mock_db])

            test_args = ["run_individual_service.py", "--user-id", "1", "--task", "sell_monitor"]
            with patch.object(sys, "argv", test_args):
                with pytest.raises(SystemExit):
                    main()

            # Verify logger was called to log the error
            assert mock_logger.called

    def test_main_closes_db_session(self):
        """Test that main() closes database session in finally block"""
        from scripts.run_individual_service import main  # noqa: PLC0415

        mock_db = MagicMock()
        mock_db.close = MagicMock()

        with (
            patch("scripts.run_individual_service.run_service_loop"),
            patch("scripts.run_individual_service.get_session") as mock_get_session,
            patch("scripts.run_individual_service.get_user_logger"),
        ):
            mock_get_session.return_value = iter([mock_db])

            test_args = ["run_individual_service.py", "--user-id", "1", "--task", "sell_monitor"]
            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit:
                    pass

            # Verify db.close() was called
            mock_db.close.assert_called_once()
