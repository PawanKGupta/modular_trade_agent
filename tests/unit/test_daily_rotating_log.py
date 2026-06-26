import logging
from datetime import datetime
from pathlib import Path

import utils.logger as logger_mod
from utils.logger import DailyRotatingFileHandler


def test_daily_rotating_file_handler_rolls_over(tmp_path: Path):
    # Setup temporary directory for log files
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    filename_pattern = str(log_dir / "test_agent_{}.log")

    # We will mock the date stamps returned
    date_stamps = ["20260627", "20260628"]
    date_index = 0

    def mock_get_today_stamp():
        return date_stamps[date_index]

    handler = DailyRotatingFileHandler(filename_pattern)
    # Inject our mock stamp getter
    handler._get_today_stamp = mock_get_today_stamp
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("TestDailyRotation")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    try:
        # Write first log
        logger.info("Log message 1")

        # Verify file test_agent_20260627.log was created and contains the message
        file1 = log_dir / "test_agent_20260627.log"
        assert file1.exists()
        with open(file1, encoding="utf-8") as f:
            content = f.read()
        assert "Log message 1\n" in content

        # Change date stamp
        date_index = 1

        # Write second log
        logger.info("Log message 2")

        # Verify file test_agent_20260628.log was created and contains the message
        file2 = log_dir / "test_agent_20260628.log"
        assert file2.exists()
        with open(file2, encoding="utf-8") as f:
            content = f.read()
        assert "Log message 2\n" in content

        # Verify old file was closed and hasn't received new content
        with open(file1, encoding="utf-8") as f:
            content1 = f.read()
        assert "Log message 2" not in content1

    finally:
        handler.close()
        logger.removeHandler(handler)


def test_get_today_stamp_format():
    handler = DailyRotatingFileHandler("test_{}.log")
    try:
        stamp = handler._get_today_stamp()
        assert len(stamp) == 8
        assert stamp.isdigit()
    finally:
        handler.close()


def test_falls_back_to_local_date_when_ist_unavailable(monkeypatch, tmp_path):
    """When the IST helper can't be imported, the handler uses the local date."""
    monkeypatch.setattr(logger_mod, "ist_now_naive", None)

    pattern = str(tmp_path / "agent_{}.log")
    handler = DailyRotatingFileHandler(pattern)
    try:
        # __init__ picked datetime.now (local) as the date source.
        assert handler._get_today_stamp() == datetime.now().strftime("%Y%m%d")
    finally:
        handler.close()
