from src.adapters.log_export import LogExportAdapter
from src.ports.events import LogEvent
from pathlib import Path


def test_export_writes_complete_snapshot_and_reports_failure(tmp_path):
    adapter = LogExportAdapter()
    payload = b"\xab" * 200
    path = tmp_path / "export.txt"
    task = adapter.export((LogEvent("RX", payload, "full", timestamp=123.25),), path)
    assert task.done.wait(2)
    assert task.error is None and task.result == path
    text = path.read_text(encoding="utf-8")
    assert "AB " * 199 + "AB" in text
    assert "123.250000" in text
    blocked = tmp_path / "blocked"
    blocked.write_text("file")
    failed = adapter.export((), blocked / "out.txt")
    assert failed.done.wait(2)
    assert failed.error
    adapter.close()
    adapter.shutdown()
    assert adapter.export((), path).error


def test_export_cleanup_failure_still_completes_and_preserves_both_errors(tmp_path, monkeypatch):
    adapter = LogExportAdapter()
    target = tmp_path / "existing.txt"
    target.write_text("previous", encoding="utf-8")
    original_unlink = Path.unlink

    def replace_denied(*args):
        raise PermissionError("replace denied")

    def cleanup_denied(path, *args, **kwargs):
        if path.parent == tmp_path and path.suffix == ".tmp":
            raise PermissionError("cleanup denied")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr("src.adapters.log_export.os.replace", replace_denied)
    monkeypatch.setattr(Path, "unlink", cleanup_denied)
    try:
        task = adapter.export((LogEvent("RX", b"\x50\x03", "test"),), target)
        assert task.done.wait(1), "An exited worker must deliver its failure"
        assert task.result is None
        assert "replace denied" in task.error and "cleanup denied" in task.error
        assert target.read_text(encoding="utf-8") == "previous"
    finally:
        adapter.shutdown()
