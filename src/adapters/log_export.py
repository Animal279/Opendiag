"""Atomic text export; full-byte conversion and disk IO stay in file workers."""

from datetime import datetime
import os
from pathlib import Path
import tempfile
import threading

from src.ports.log_export import LogExportPort
from src.ports.projects import ProjectTask


class LogExportAdapter(LogExportPort):
    def __init__(self):
        self._threads = []
        self._closed = False

    def export(self, events, path):
        task = ProjectTask()
        path = Path(path)
        if self._closed:
            task.error = "日志导出服务已关闭"
            task.done.set()
            return task
        snapshot = tuple(events)
        def write():
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, suffix=".tmp", delete=False) as output:
                    temporary = Path(output.name)
                    for event in snapshot:
                        data = event.data.hex(" ").upper() if event.data is not None else ""
                        output.write(f"{datetime.fromtimestamp(event.timestamp).isoformat(timespec='milliseconds')}\t{event.timestamp:.6f}\t{event.level}\t{data}\t{event.description}\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
                temporary = None
                task.result = path
            except OSError as exc:
                task.error = str(exc)
            finally:
                try:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
                except OSError as exc:
                    cleanup_error = f"临时日志清理失败（{temporary}）：{exc}"
                    task.error = f"{task.error}; {cleanup_error}" if task.error else cleanup_error
                finally:
                    task.done.set()
        self._threads[:] = [thread for thread in self._threads if thread.is_alive()]
        thread = threading.Thread(target=write, name="log-export", daemon=True)
        self._threads.append(thread)
        thread.start()
        return task

    def close(self):
        self._closed = True

    def shutdown(self):
        self.close()
        for thread in self._threads:
            thread.join(timeout=5)
        if any(thread.is_alive() for thread in self._threads):
            raise RuntimeError("Log export worker did not stop")
