"""Central logging setup: size + daily rotation, 9-day retention, secret redaction.

Environment variables:
    LOG_DIR        directory for log files (default: <project>/logs)
    LOG_LEVEL      DEBUG / INFO / WARNING / ERROR (default: INFO)
    LOG_MAX_BYTES  max size of one log file before rotation (default: 5 MiB)
"""

import contextvars
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from logging.handlers import BaseRotatingHandler
from zoneinfo import ZoneInfo

LOG_TZ = ZoneInfo("Asia/Tehran")
LOG_FILE_NAME = "bot.log"
RETENTION_DAYS = 9
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
MAX_MESSAGE_CHARS = 10000
CLEANUP_INTERVAL_SECONDS = 60 * 60

request_id_var = contextvars.ContextVar("request_id", default="-")


def new_request_id() -> str:
    """Create a short id and bind it to the current context."""
    request_id = uuid.uuid4().hex[:8]
    request_id_var.set(request_id)
    return request_id


def _today() -> str:
    return datetime.now(LOG_TZ).strftime("%Y-%m-%d")


class RedactingContextFilter(logging.Filter):
    """Attach the request id, mask secrets and cap message length."""

    PATTERNS = (
        (re.compile(r"/bot\d+:[A-Za-z0-9_\-]+"), "/bot<redacted>"),
        (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-<redacted>"),
        (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1<redacted>"),
    )

    def __init__(self):
        super().__init__()
        self._secrets = []

    def _known_secrets(self):
        if not self._secrets:
            for name in ("BALE_BOT_TOKEN", "AI_API_KEY"):
                value = os.environ.get(name, "").strip()
                if len(value) >= 8:
                    self._secrets.append(value)
        return self._secrets

    def _clean(self, text: str) -> str:
        for secret in self._known_secrets():
            text = text.replace(secret, "<redacted>")
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def filter(self, record):
        record.request_id = request_id_var.get()
        message = self._clean(record.getMessage())
        if len(message) > MAX_MESSAGE_CHARS:
            message = message[:MAX_MESSAGE_CHARS] + "...[truncated]"
        record.msg = message
        record.args = None
        if record.exc_info:
            record.exc_text = self._clean(
                logging.Formatter().formatException(record.exc_info)
            )
            record.exc_info = None
        return True


class TehranFormatter(logging.Formatter):
    """Formatter with timezone-aware Tehran timestamps."""

    def formatTime(self, record, datefmt=None):
        moment = datetime.fromtimestamp(record.created, LOG_TZ)
        return moment.strftime("%Y-%m-%d %H:%M:%S") + f".{int(record.msecs):03d}"


class SizeAndDateRotatingFileHandler(BaseRotatingHandler):
    """Rotate at a size limit and at day change; delete archives after N days.

    Active file: bot.log. Archives: bot.log.YYYY-MM-DD.N (date = day of content).
    """

    def __init__(self, filename, max_bytes, retention_days=RETENTION_DAYS):
        super().__init__(filename, "a", encoding="utf-8", delay=True)
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self._last_cleanup = 0.0
        self._file_day = self._initial_file_day()
        self._cleanup_expired_files()

    def _initial_file_day(self) -> str:
        try:
            mtime = os.path.getmtime(self.baseFilename)
            return datetime.fromtimestamp(mtime, LOG_TZ).strftime("%Y-%m-%d")
        except OSError:
            return _today()

    def shouldRollover(self, record):
        if self._file_day != _today():
            return True
        if self.max_bytes <= 0:
            return False
        if self.stream is None:
            self.stream = self._open()
        self.stream.seek(0, os.SEEK_END)
        size = self.stream.tell()
        if size == 0:
            return False
        message = (self.format(record) + self.terminator).encode("utf-8", "replace")
        return size + len(message) > self.max_bytes

    def _next_archive_name(self) -> str:
        index = 1
        while True:
            candidate = f"{self.baseFilename}.{self._file_day}.{index}"
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        try:
            if os.path.exists(self.baseFilename) and os.path.getsize(self.baseFilename):
                os.replace(self.baseFilename, self._next_archive_name())
        except OSError:
            pass
        self._file_day = _today()
        self.stream = self._open()
        self._cleanup_expired_files()

    def emit(self, record):
        super().emit(record)
        if time.time() - self._last_cleanup >= CLEANUP_INTERVAL_SECONDS:
            self._cleanup_expired_files()

    def _cleanup_expired_files(self):
        self._last_cleanup = time.time()
        cutoff = datetime.now(LOG_TZ) - timedelta(days=self.retention_days)
        directory = os.path.dirname(self.baseFilename)
        prefix = os.path.basename(self.baseFilename) + "."
        try:
            names = os.listdir(directory)
        except OSError:
            return
        for name in names:
            if not name.startswith(prefix):
                continue
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", name[len(prefix):]):
                continue
            path = os.path.join(directory, name)
            try:
                last_write = datetime.fromtimestamp(os.path.getmtime(path), LOG_TZ)
                if last_write < cutoff:
                    os.remove(path)
            except OSError:
                continue


_configured = False


def setup_logging() -> logging.Logger:
    """Configure logging once and return the application logger."""
    global _configured
    app_logger = logging.getLogger("bot")
    if _configured:
        return app_logger

    log_dir = os.environ.get("LOG_DIR", "").strip() or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs"
    )
    level = getattr(
        logging, os.environ.get("LOG_LEVEL", "INFO").strip().upper(), logging.INFO
    )
    try:
        max_bytes = int(os.environ.get("LOG_MAX_BYTES", DEFAULT_MAX_BYTES))
    except ValueError:
        max_bytes = DEFAULT_MAX_BYTES

    os.makedirs(log_dir, exist_ok=True)
    handler = SizeAndDateRotatingFileHandler(
        os.path.join(log_dir, LOG_FILE_NAME), max_bytes=max_bytes
    )
    handler.setFormatter(
        TehranFormatter(
            "%(asctime)s | %(levelname)-8s | pid=%(process)d | req=%(request_id)s | "
            "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
    )
    handler.addFilter(RedactingContextFilter())

    app_logger.setLevel(level)
    app_logger.propagate = False
    app_logger.addHandler(handler)

    for library in ("requests", "urllib3", "openai", "httpx", "werkzeug"):
        library_logger = logging.getLogger(library)
        library_logger.setLevel(logging.WARNING)
        library_logger.propagate = False
        library_logger.addHandler(handler)

    _configured = True
    app_logger.info(
        "Logging started | dir=%s level=%s max_bytes=%s retention_days=%s",
        log_dir,
        logging.getLevelName(level),
        max_bytes,
        RETENTION_DAYS,
    )
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the application logger, e.g. get_logger('ai')."""
    setup_logging()
    return logging.getLogger(f"bot.{name}")
