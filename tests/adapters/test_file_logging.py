from pathlib import Path
import io

from src.adapters.file_logging import BackgroundFileLogging


def test_worker_drains_and_releases_file(tmp_path: Path):
    runtime = BackgroundFileLogging(tmp_path)
    assert runtime.ready.wait(2)
    assert runtime.error is None
    runtime.logger.warning("骨架日志验证")
    runtime.close()
    runtime.close()
    assert runtime.stopped.is_set()
    assert not runtime.thread.is_alive()
    assert "骨架日志验证" in runtime.log_file.read_text(encoding="utf-8")
    # Windows rename proves no lingering FileHandler file lock.
    runtime.log_file.rename(tmp_path / "closed.log")


def test_unwritable_directory_reports_failure(tmp_path: Path):
    blocked = tmp_path / "file"
    blocked.write_text("not a directory", encoding="utf-8")
    runtime = BackgroundFileLogging(blocked)
    assert runtime.ready.wait(2)
    assert runtime.stopped.wait(2)
    assert isinstance(runtime.error, OSError)
    runtime.close()


def test_write_failure_sets_error_and_stops_worker(tmp_path, monkeypatch):
    class FailingStream(io.StringIO):
        def write(self, text):
            raise OSError("injected disk full")

    stream = FailingStream()
    monkeypatch.setattr(
        "src.adapters.file_logging._StrictRotatingFileHandler._open", lambda self: stream
    )
    runtime = BackgroundFileLogging(tmp_path)
    assert runtime.ready.wait(2)
    runtime.logger.error("write must fail")
    assert runtime.stopped.wait(2)
    assert isinstance(runtime.error, OSError)
    assert "disk full" in str(runtime.error)
    runtime.close()
    assert stream.closed
