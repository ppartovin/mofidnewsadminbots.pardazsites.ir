"""Configure the bot's size- and age-rotated file logging."""

import logging
import os
import time
from logging.handlers import RotatingFileHandler


class SizeAndAgeRotatingFileHandler(RotatingFileHandler):
    """Rotate logs at a size limit and remove rotated files after 14 days."""

    RETENTION_SECONDS = 14 * 24 * 60 * 60
    CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60

    def __init__(self, filename, max_bytes):
        super().__init__(filename, maxBytes=max_bytes, backupCount=0, encoding="utf-8")
        self._last_cleanup = 0.0
        self._cleanup_expired_files()

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if os.path.exists(self.baseFilename):
            archive = f"{self.baseFilename}.{time.time_ns()}"
            os.replace(self.baseFilename, archive)
        if not self.delay:
            self.stream = self._open()

    def shouldRollover(self, record):
        if self.maxBytes <= 0:
            return False
        if self.stream is None:
            self.stream = self._open()
        self.stream.seek(0, os.SEEK_END)
        current_size = self.stream.tell()
        message = (self.format(record) + self.terminator).encode(
            self.encoding or "utf-8", self.errors or "strict"
        )
        return current_size + len(message) > self.maxBytes

    def emit(self, record):
        super().emit(record)
        now = time.time()
        if now - self._last_cleanup >= self.CLEANUP_INTERVAL_SECONDS:
            self._cleanup_expired_files(now)

    def _cleanup_expired_files(self, now=None):
        now = time.time() if now is None else now
        cutoff = now - self.RETENTION_SECONDS
        directory = os.path.dirname(os.path.abspath(self.baseFilename))
        prefix = os.path.basename(self.baseFilename) + "."
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    suffix = entry.name[len(prefix):] if entry.name.startswith(prefix) else ""
                    if suffix.isdigit() and entry.is_file():
                        try:
                            if entry.stat().st_mtime < cutoff:
                                os.remove(entry.path)
                        except FileNotFoundError:
                            pass
        except OSError:
            logging.getLogger(__name__).exception("Could not clean up expired log files")
        self._last_cleanup = now


_logger = logging.getLogger("bot")
_logger.setLevel(logging.INFO)
_logger.propagate = False
_logger.addHandler(
    SizeAndAgeRotatingFileHandler(
        os.path.join(os.path.dirname(__file__), "bot.log"),
        max_bytes=5 * 1024 * 1024,
    )
)


def log(text):
    """Write one log record, keeping it below the configured file size limit."""
    _logger.info("%.10000s", str(text))
