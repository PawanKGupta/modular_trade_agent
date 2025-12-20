"""JSONL file-based log reader used by log endpoints."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.infrastructure.db.timezone_utils import ist_now


class FileLogReader:
    """
    File Log Reader for JSONL activity logs.

    Reads per-user JSONL logs with filtering and tail support.
    """

    def __init__(self, base_dir: Path | str = "logs"):
        self.base_dir = Path(base_dir)

    def _iter_log_files(self, user_id: int, log_type: str, days_back: int) -> list[Path]:
        user_dir = self.base_dir / "users" / f"user_{user_id}"
        if not user_dir.exists():
            return []

        end_date = ist_now().date()
        start_date = end_date - timedelta(days=days_back - 1)

        files: list[Path] = []
        current = end_date
        while current >= start_date:
            date_str = current.strftime("%Y%m%d")
            candidate = user_dir / f"{log_type}_{date_str}.jsonl"
            if candidate.exists():
                files.append(candidate)
            current -= timedelta(days=1)
        return files  # Newest date first

    @staticmethod
    def _parse_line(line: str, fallback_time: datetime) -> dict[str, Any] | None:
        line = line.strip()
        if not line:
            return None
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        ts_raw = data.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(ts_raw) if ts_raw else fallback_time
        except Exception:
            timestamp = fallback_time

        required = {"level", "module", "message", "user_id"}
        if not required.issubset(data.keys()):
            return None

        return {
            "id": data.get("id"),
            "user_id": data["user_id"],
            "level": data["level"],
            "module": data["module"],
            "message": data["message"],
            "context": data.get("context"),
            "timestamp": timestamp,
        }

    def read_logs(  # noqa: PLR0913
        self,
        user_id: int,
        *,
        level: str | None = None,
        module: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        search: str | None = None,
        limit: int = 500,
        days_back: int = 14,
    ) -> list[dict[str, Any]]:
        files = self._iter_log_files(user_id, log_type="service", days_back=days_back)
        results: list[dict[str, Any]] = []
        fallback_time = ist_now()

        for path in files:
            try:
                with path.open("r", encoding="utf-8") as f:
                    buffer: deque[dict[str, Any]] = deque(maxlen=limit)
                    line_no = 0
                    for line in f:
                        line_no += 1
                        parsed = self._parse_line(line, fallback_time)
                        if not parsed:
                            continue
                        if not parsed.get("id"):
                            parsed["id"] = f"{path.name}:{line_no}"

                        if level and parsed["level"].upper() != level.upper():
                            continue
                        if module and module.lower() not in parsed["module"].lower():
                            continue
                        if start_time and parsed["timestamp"] < start_time:
                            continue
                        if end_time and parsed["timestamp"] > end_time:
                            continue
                        if (
                            search
                            and search.lower()
                            not in json.dumps(
                                {"message": parsed["message"], "context": parsed.get("context")}
                            ).lower()
                        ):
                            continue

                        buffer.append(parsed)

                    if buffer:
                        results.extend(buffer)

                if len(results) >= limit:
                    break  # already have enough from newest files
            except (OSError, UnicodeDecodeError):
                continue

        # keep only latest `limit` and return newest-first
        results = results[-limit:]
        return list(reversed(results))

    def read_error_logs(  # noqa: PLR0913
        self,
        user_id: int,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        search: str | None = None,
        limit: int = 500,
        days_back: int = 30,
    ) -> list[dict[str, Any]]:
        files = self._iter_log_files(user_id, log_type="errors", days_back=days_back)
        results: list[dict[str, Any]] = []
        fallback_time = ist_now()

        for path in files:
            try:
                with path.open("r", encoding="utf-8") as f:
                    buffer: deque[dict[str, Any]] = deque(maxlen=limit)
                    line_no = 0
                    for line in f:
                        line_no += 1
                        parsed = self._parse_line(line, fallback_time)
                        if not parsed:
                            continue
                        if parsed["level"].upper() not in ("ERROR", "CRITICAL"):
                            continue
                        if not parsed.get("id"):
                            parsed["id"] = f"{path.name}:{line_no}"

                        if start_time and parsed["timestamp"] < start_time:
                            continue
                        if end_time and parsed["timestamp"] > end_time:
                            continue
                        if (
                            search
                            and search.lower()
                            not in json.dumps(
                                {"message": parsed["message"], "context": parsed.get("context")}
                            ).lower()
                        ):
                            continue

                        buffer.append(parsed)

                    if buffer:
                        results.extend(buffer)

                if len(results) >= limit:
                    break
            except (OSError, UnicodeDecodeError):
                continue

        results = results[-limit:]
        return list(reversed(results))

    def tail_logs(
        self,
        user_id: int,
        *,
        log_type: str = "service",
        tail_lines: int = 200,
    ) -> list[dict[str, Any]]:
        files = self._iter_log_files(user_id, log_type=log_type, days_back=1)
        if not files:
            return []

        path = files[0]
        fallback_time = ist_now()
        try:
            with path.open("r", encoding="utf-8") as f:
                buffer = deque(f, maxlen=tail_lines)
            results: list[dict[str, Any]] = []
            line_no = 0
            for line in buffer:
                line_no += 1
                parsed = self._parse_line(line, fallback_time)
                if not parsed:
                    continue
                if not parsed.get("id"):
                    parsed["id"] = f"{path.name}:{line_no}"
                results.append(parsed)
            return list(reversed(results))
        except (OSError, UnicodeDecodeError):
            return []
