import logging
import os
import sys
from datetime import datetime

try:
    from src.infrastructure.db.timezone_utils import ist_now_naive
except ImportError:
    ist_now_naive = None  # type: ignore[assignment]

# Try to ensure UTF-8 capable stdout to avoid Unicode errors in console
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: S110
    pass

# Create a logger object
logger = logging.getLogger("TradeAgent")
logger.setLevel(logging.DEBUG)  # Set to DEBUG for full detail, change to INFO or WARNING in prod


# Unicode-safe formatter (replaces unsupported chars for the active console encoding)
class UnicodeSafeFormatter(logging.Formatter):
    def format(self, record):
        s = super().format(record)
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            return s.encode(enc, errors="replace").decode(enc, errors="replace")
        except Exception:
            return s


# Formatter for logs
formatter = UnicodeSafeFormatter(
    "%(asctime)s - %(levelname)s - %(module)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # Info+ to console
console_handler.setFormatter(formatter)


class DailyRotatingFileHandler(logging.FileHandler):
    """
    A file handler that rotates daily at midnight (in IST if available, or local time).
    The file name dynamically incorporates the current date stamp on each log write.
    """

    def __init__(self, filename_pattern: str, encoding: str = "utf-8"):
        self.filename_pattern = filename_pattern
        self.encoding = encoding

        if ist_now_naive is not None:
            self._get_date_fn = ist_now_naive
        else:
            self._get_date_fn = datetime.now

        self.current_stamp = self._get_today_stamp()

        filename = self.filename_pattern.format(self.current_stamp)
        super().__init__(filename, encoding=self.encoding)

    def _get_today_stamp(self) -> str:
        return self._get_date_fn().strftime("%Y%m%d")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            today_stamp = self._get_today_stamp()
            if today_stamp != self.current_stamp:
                self.current_stamp = today_stamp
                new_filename = self.filename_pattern.format(today_stamp)
                self.baseFilename = os.path.abspath(new_filename)

                # Close the current stream; self.flush() re-acquires the lock,
                # which is safe since the lock is reentrant (RLock)
                if self.stream:
                    try:
                        self.flush()
                        self.stream.close()
                    except Exception:  # noqa: S110
                        pass
                self.stream = None
        except Exception:  # noqa: S110
            pass
        super().emit(record)


logger.addHandler(console_handler)

# File logging is optional: subprocesses / containers often run with a read-only or
# root-owned `logs/` mount (PermissionError). Console logging still works.
_log_pattern = "logs/trade_agent_{}.log"
try:
    os.makedirs("logs", exist_ok=True)
    file_handler = DailyRotatingFileHandler(_log_pattern, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(module)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    logger.addHandler(file_handler)
except OSError as exc:
    logger.warning("File logging disabled (%s): %s", _log_pattern, exc)
