"""P1 log writer: bounded queue ownership, file IO only in a daemon worker."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Empty, Full, Queue
import sys
from threading import Event, Thread
from uuid import uuid4


class _QueueHandler(logging.Handler):
    def __init__(self, records: Queue, closing: Event, on_error):
        super().__init__()
        self._records = records
        self._closing = closing
        self._on_error = on_error
        self._overflow_reported = Event()

    def emit(self, record: logging.LogRecord) -> None:
        if self._closing.is_set():
            return
        try:
            self._records.put_nowait(record)
        except Full:
            # Do not block Qt or echo potentially sensitive record contents.
            print("OpenDiag 日志队列已满，本条日志未写入。", file=sys.stderr)
            if not self._overflow_reported.is_set():
                self._overflow_reported.set()
                self._on_error("日志队列已满，部分记录未写入")


class _StrictRotatingFileHandler(RotatingFileHandler):
    def handleError(self, record: logging.LogRecord) -> None:
        """Propagate disk failures to the owning writer, not logging's stderr dump."""
        error = sys.exception()
        if error is not None:
            raise error
        raise RuntimeError("日志写入出现未知错误")


class _WireFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        data = getattr(record, "wire_data", None)
        if data is not None:
            text += " | " + data.hex(" ").upper()
        return text


class BackgroundFileLogging:
    """One consumer owns the file; callers only hand off LogRecords.

    close() drains and joins after the Qt event loop has returned. This is a
    local infrastructure choice, not a claim about the original log format.
    """

    def __init__(self, logs_dir: Path, *, on_error=None):
        self._records: Queue[logging.LogRecord] = Queue(maxsize=2048)
        self._closing = Event()
        self.ready = Event()
        self.stopped = Event()
        self.error: OSError | None = None  # Read only after ready/stopped.
        self.log_file = logs_dir / "opendiag.log"
        self._on_error = on_error or (lambda message: None)
        self.logger = logging.getLogger(f"opendiag.runtime.{uuid4().hex}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self._handler = _QueueHandler(self._records, self._closing, self._on_error)
        self.logger.addHandler(self._handler)
        self.thread = Thread(target=self._write, name="opendiag-log-writer", daemon=True)
        self.thread.start()

    def _write(self) -> None:
        handler = None
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = _StrictRotatingFileHandler(
                self.log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(_WireFormatter("%(asctime)s [%(levelname)s] source=%(created).6f %(message)s"))
            self.ready.set()
            while not self._closing.is_set() or not self._records.empty():
                try:
                    record = self._records.get(timeout=0.05)
                except Empty:
                    continue
                try:
                    handler.handle(record)
                finally:
                    self._records.task_done()
        except OSError as exc:
            self.error = exc
            self._closing.set()
            print(f"OpenDiag 日志写入失败：{exc}", file=sys.stderr)
            self._on_error(f"日志写入失败：{exc}")
        finally:
            self.ready.set()
            if handler is not None:
                handler.close()
            self.stopped.set()

    def close(self) -> None:
        self._closing.set()
        self.logger.removeHandler(self._handler)
        self._handler.close()
        self.thread.join(timeout=2.0)
        if self.thread.is_alive():
            raise RuntimeError("日志写线程尚未退出")
