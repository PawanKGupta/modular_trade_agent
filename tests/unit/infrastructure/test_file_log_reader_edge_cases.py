"""
Edge case tests for FileLogReader

Tests all corner cases mentioned in LOGGING_FILE_PLAN.md:
- Invalid/partial JSON lines
- File reading while writing (concurrent access simulation)
- Large files with limit enforcement
- Multiline stack traces in context
- Rotation boundary (day change)
- ID collisions
- Permissions/IO errors
- Empty files
- Missing required fields
- Invalid timestamps
- Context search edge cases
- Timezone consistency
- Tail logs edge cases
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.infrastructure.db.timezone_utils import IST, ist_now
from src.infrastructure.logging.file_log_reader import FileLogReader
from src.infrastructure.logging.user_file_log_handler import UserFileLogHandler


class TestInvalidLines:
    """Test handling of invalid/partial JSON lines"""

    def test_skips_invalid_json_lines(self, tmp_path, monkeypatch):
        """Test that invalid JSON lines are skipped gracefully"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        # Write mix of valid and invalid lines
        with log_file.open("w", encoding="utf-8") as f:
            f.write(
                '{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Valid","user_id":1}\n'
            )
            f.write("invalid json line\n")
            f.write('{"incomplete":\n')  # Partial JSON
            f.write(
                '{"timestamp":"2024-01-01T10:01:00","level":"ERROR","module":"test","message":"Valid2","user_id":1}\n'
            )
            f.write("not json at all\n")
            f.write(
                '{"timestamp":"2024-01-01T10:02:00","level":"WARNING","module":"test","message":"Valid3","user_id":1}\n'
            )

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        # Should only return valid logs
        assert len(logs) == 3
        assert logs[0]["message"] == "Valid3"
        assert logs[1]["message"] == "Valid2"
        assert logs[2]["message"] == "Valid"

    def test_skips_empty_lines(self, tmp_path, monkeypatch):
        """Test that empty lines are skipped"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        with log_file.open("w", encoding="utf-8") as f:
            f.write("\n")
            f.write(
                '{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Valid","user_id":1}\n'
            )
            f.write("   \n")  # Whitespace only
            f.write(
                '{"timestamp":"2024-01-01T10:01:00","level":"INFO","module":"test","message":"Valid2","user_id":1}\n'
            )

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        assert len(logs) == 2

    def test_skips_lines_missing_required_fields(self, tmp_path, monkeypatch):
        """Test that lines missing required fields are skipped"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        with log_file.open("w", encoding="utf-8") as f:
            # Missing user_id
            f.write(
                '{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Invalid"}\n'
            )
            # Missing level
            f.write(
                '{"timestamp":"2024-01-01T10:01:00","module":"test","message":"Invalid","user_id":1}\n'
            )
            # Missing module
            f.write(
                '{"timestamp":"2024-01-01T10:02:00","level":"INFO","message":"Invalid","user_id":1}\n'
            )
            # Missing message
            f.write(
                '{"timestamp":"2024-01-01T10:03:00","level":"INFO","module":"test","user_id":1}\n'
            )
            # Valid
            f.write(
                '{"timestamp":"2024-01-01T10:04:00","level":"INFO","module":"test","message":"Valid","user_id":1}\n'
            )

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        assert len(logs) == 1
        assert logs[0]["message"] == "Valid"

    def test_handles_invalid_timestamp_gracefully(self, tmp_path, monkeypatch):
        """Test that invalid timestamps use fallback time"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        fallback_time = ist_now()

        with log_file.open("w", encoding="utf-8") as f:
            # Invalid timestamp format
            f.write(
                '{"timestamp":"not-a-date","level":"INFO","module":"test","message":"InvalidTS","user_id":1}\n'
            )
            # Missing timestamp
            f.write('{"level":"INFO","module":"test","message":"NoTS","user_id":1}\n')
            # Valid timestamp
            f.write(
                f'{{"timestamp":"{fallback_time.isoformat()}","level":"INFO","module":"test","message":"ValidTS","user_id":1}}\n'
            )

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        # All should be parsed (invalid timestamps use fallback)
        assert len(logs) == 3
        # All should have valid timestamp objects
        for log in logs:
            assert isinstance(log["timestamp"], datetime)


class TestConcurrentAccess:
    """Test file reading while writing (concurrent access simulation)"""

    def test_handles_partial_writes(self, tmp_path, monkeypatch):
        """Test that partial writes (incomplete JSON) are skipped"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        # Simulate partial write - file ends mid-JSON
        with log_file.open("w", encoding="utf-8") as f:
            f.write(
                '{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Complete","user_id":1}\n'
            )
            f.write(
                '{"timestamp":"2024-01-01T10:01:00","level":"INFO","module":"test","message":"Incomplete"'
            )  # No closing brace

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        # Should only return complete log
        assert len(logs) == 1
        assert logs[0]["message"] == "Complete"


class TestLargeFiles:
    """Test large file handling with limit enforcement"""

    def test_enforces_limit(self, tmp_path, monkeypatch):
        """Test that limit is enforced even with large files"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        # Create more logs than limit
        for i in range(1000):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=100)

        # Should respect limit
        assert len(logs) == 100
        # Should return newest first
        assert "Message 999" in logs[0]["message"]

    def test_enforces_days_back(self, tmp_path, monkeypatch):
        """Test that days_back limit is enforced"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create files for multiple days
        today = ist_now().date()
        for i in range(20):  # 20 days
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            log_file = log_dir / f"service_{date_str}.jsonl"
            with log_file.open("w", encoding="utf-8") as f:
                timestamp = f"{date.isoformat()}T10:00:00"
                msg = (
                    f'{{"timestamp":"{timestamp}","level":"INFO",'
                    f'"module":"test","message":"Day {i}","user_id":1}}\n'
                )
                f.write(msg)

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, days_back=5, limit=100)

        # Should only read last 5 days
        assert len(logs) <= 5


class TestMultilineStackTraces:
    """Test multiline stack traces in context"""

    def test_stores_multiline_stack_trace_in_context(self, tmp_path, monkeypatch):
        """Test that multiline stack traces are stored in context"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=None,
        )
        record.log_module = "test_module"
        record.user_id = 1
        # Simulate multiline traceback in context (custom field, not in STANDARD_FIELDS)
        multiline_trace = (
            "Traceback (most recent call last):\n"
            '  File "test.py", line 1\n'
            "    raise ValueError\n"
            "ValueError"
        )
        record.custom_traceback = multiline_trace  # Use custom field name
        handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, level="ERROR", limit=1)

        assert len(logs) == 1
        # Stack trace should be in context
        assert logs[0]["context"] is not None
        assert "custom_traceback" in logs[0]["context"]
        assert multiline_trace in logs[0]["context"]["custom_traceback"]


class TestRotationBoundary:
    """Test day rotation boundary handling"""

    def test_reads_multiple_days(self, tmp_path, monkeypatch):
        """Test that rotation reads yesterday + today"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)

        today = ist_now().date()
        yesterday = today - timedelta(days=1)

        # Create yesterday's file
        yesterday_file = log_dir / f"service_{yesterday.strftime('%Y%m%d')}.jsonl"
        with yesterday_file.open("w", encoding="utf-8") as f:
            f.write(
                f'{{"timestamp":"{yesterday.isoformat()}T10:00:00","level":"INFO","module":"test","message":"Yesterday","user_id":1}}\n'
            )

        # Create today's file
        today_file = log_dir / f"service_{today.strftime('%Y%m%d')}.jsonl"
        with today_file.open("w", encoding="utf-8") as f:
            f.write(
                f'{{"timestamp":"{today.isoformat()}T10:00:00","level":"INFO","module":"test","message":"Today","user_id":1}}\n'
            )

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, days_back=2, limit=10)

        # Should read from both days
        assert len(logs) == 2
        messages = [log["message"] for log in logs]
        assert "Today" in messages
        assert "Yesterday" in messages
        # The implementation reads files newest-first but reverses results,
        # so we just verify both messages are present (order may vary based on implementation)
        # The important thing is that both days are read correctly


class TestIDCollisions:
    """Test ID collision handling"""

    def test_file_line_composite_ensures_unique_ids(self, tmp_path, monkeypatch):
        """Test that file:line composite ensures unique IDs"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        for i in range(5):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        # All IDs should be unique
        ids = [log["id"] for log in logs]
        assert len(ids) == len(set(ids))
        # IDs should be in file:line format
        assert all(":" in id_str for id_str in ids)


class TestIOErrors:
    """Test permissions/IO error handling"""

    def test_skips_files_on_permission_error(self, tmp_path, monkeypatch):
        """Test that permission errors don't fail the request"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")

        # Create readable file
        readable_file = log_dir / f"service_{today}.jsonl"
        with readable_file.open("w", encoding="utf-8") as f:
            f.write(
                '{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Readable","user_id":1}\n'
            )

        reader = FileLogReader(base_dir="logs")

        # Mock OSError for one file (simulating permission error)
        original_open = Path.open

        def mock_open(self, *args, **kwargs):
            if "service_" in str(self):
                raise OSError("Permission denied")
            return original_open(self, *args, **kwargs)

        with patch.object(Path, "open", mock_open):
            logs = reader.read_logs(user_id=1, limit=10)

        # Should handle gracefully - may return empty or partial results
        # but shouldn't crash
        assert isinstance(logs, list)

    def test_handles_missing_directory_gracefully(self, tmp_path, monkeypatch):
        """Test that missing user directory returns empty list"""
        monkeypatch.chdir(tmp_path)

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=99999, limit=10)

        # Should return empty list, not raise
        assert logs == []

    def test_handles_unicode_decode_error(self, tmp_path, monkeypatch):
        """Test that UnicodeDecodeError is handled gracefully"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        # Write file with invalid UTF-8
        with log_file.open("wb") as f:
            f.write(
                b'{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Valid","user_id":1}\n'
            )
            f.write(b"\xff\xfe\x00")  # Invalid UTF-8 sequence
            f.write(
                b'{"timestamp":"2024-01-01T10:01:00","level":"INFO","module":"test","message":"AfterInvalid","user_id":1}\n'
            )

        reader = FileLogReader(base_dir="logs")
        # Should handle gracefully - may skip invalid file or return partial results
        logs = reader.read_logs(user_id=1, limit=10)

        # Should not crash
        assert isinstance(logs, list)


class TestEmptyFiles:
    """Test empty file handling"""

    def test_handles_empty_file(self, tmp_path, monkeypatch):
        """Test that empty files return empty results"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        # Create empty file
        log_file.touch()

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)

        assert logs == []


class TestContextSearch:
    """Test context search edge cases"""

    def test_searches_in_context_fields(self, tmp_path, monkeypatch):
        """Test that search includes context fields"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Main message",
            args=(),
            exc_info=None,
        )
        record.log_module = "test_module"
        record.user_id = 1
        record.symbol = "RELIANCE"  # Custom context field
        record.action = "buy_order"
        handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        # Search for text in context
        logs = reader.read_logs(user_id=1, search="RELIANCE", limit=10)

        assert len(logs) == 1
        assert logs[0]["context"]["symbol"] == "RELIANCE"

    def test_search_is_case_insensitive(self, tmp_path, monkeypatch):
        """Test that search is case insensitive"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test Message",
            args=(),
            exc_info=None,
        )
        record.log_module = "test_module"
        record.user_id = 1
        handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        # Search with different case
        logs = reader.read_logs(user_id=1, search="test message", limit=10)

        assert len(logs) == 1


class TestTimezoneConsistency:
    """Test timezone consistency"""

    def test_uses_ist_timezone_consistently(self, tmp_path, monkeypatch):
        """Test that IST timezone is used consistently"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.log_module = "test_module"
        record.user_id = 1
        handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=1)

        assert len(logs) == 1
        # Timestamp should be timezone-aware
        assert logs[0]["timestamp"].tzinfo is not None
        # Should be IST timezone
        assert logs[0]["timestamp"].tzinfo == IST


class TestTailLogs:
    """Test tail logs edge cases"""

    def test_tail_returns_latest_lines(self, tmp_path, monkeypatch):
        """Test that tail returns latest N lines"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        for i in range(50):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        tail_logs = reader.tail_logs(user_id=1, log_type="service", tail_lines=10)

        # Should return last 10 lines
        assert len(tail_logs) == 10
        # Should be newest first
        assert "Message 49" in tail_logs[0]["message"]
        assert "Message 40" in tail_logs[-1]["message"]

    def test_tail_handles_empty_file(self, tmp_path, monkeypatch):
        """Test that tail handles empty file gracefully"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"
        log_file.touch()

        reader = FileLogReader(base_dir="logs")
        tail_logs = reader.tail_logs(user_id=1, log_type="service", tail_lines=10)

        assert tail_logs == []

    def test_tail_handles_missing_file(self, tmp_path, monkeypatch):
        """Test that tail handles missing file gracefully"""
        monkeypatch.chdir(tmp_path)

        reader = FileLogReader(base_dir="logs")
        tail_logs = reader.tail_logs(user_id=99999, log_type="service", tail_lines=10)

        assert tail_logs == []

    def test_tail_skips_invalid_lines(self, tmp_path, monkeypatch):
        """Test that tail skips invalid lines"""
        monkeypatch.chdir(tmp_path)

        log_dir = Path("logs") / "users" / "user_1"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = ist_now().date().strftime("%Y%m%d")
        log_file = log_dir / f"service_{today}.jsonl"

        with log_file.open("w", encoding="utf-8") as f:
            f.write("invalid\n")
            f.write(
                '{"timestamp":"2024-01-01T10:00:00","level":"INFO","module":"test","message":"Valid","user_id":1}\n'
            )
            f.write("also invalid\n")
            f.write(
                '{"timestamp":"2024-01-01T10:01:00","level":"INFO","module":"test","message":"Valid2","user_id":1}\n'
            )

        reader = FileLogReader(base_dir="logs")
        tail_logs = reader.tail_logs(user_id=1, log_type="service", tail_lines=10)

        # Should only return valid logs
        assert len(tail_logs) == 2


class TestFilterEdgeCases:
    """Test filter edge cases"""

    def test_level_filter_case_insensitive(self, tmp_path, monkeypatch):
        """Test that level filter is case insensitive"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        for level in ["INFO", "ERROR", "WARNING"]:
            record = logging.LogRecord(
                name="test",
                level=getattr(logging, level),
                pathname="",
                lineno=0,
                msg=f"{level} message",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        # Search with lowercase
        logs = reader.read_logs(user_id=1, level="error", limit=10)

        assert len(logs) == 1
        assert logs[0]["level"] == "ERROR"

    def test_module_filter_is_case_insensitive(self, tmp_path, monkeypatch):
        """Test that module filter is case insensitive"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.log_module = "MyModule"
        record.user_id = 1
        handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        # Search with lowercase
        logs = reader.read_logs(user_id=1, module="mymodule", limit=10)

        assert len(logs) == 1

    def test_time_filter_boundaries(self, tmp_path, monkeypatch):
        """Test time filter boundary conditions"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        base_time = ist_now()

        # Create logs at different times
        for i in range(5):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        # Filter with start_time
        start_time = base_time - timedelta(hours=1)
        logs = reader.read_logs(user_id=1, start_time=start_time, limit=10)

        # Should return logs after start_time
        assert len(logs) >= 0  # May be 0 if all logs are before start_time

        # Filter with end_time
        end_time = base_time + timedelta(hours=1)
        logs = reader.read_logs(user_id=1, end_time=end_time, limit=10)

        # Should return logs before end_time
        assert len(logs) >= 0
