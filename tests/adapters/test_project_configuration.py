from dataclasses import replace
import json
from pathlib import Path
import threading

import pytest

from src.adapters.project_configuration import ProjectConfigurationAdapter
from src.core.app_paths import AppPaths
from src.core.config_manager import ConfigManager
from tests.core.test_config_manager import write_project
from tests.domain.test_connection_settings import sample_config


def finish(adapter, task):
    assert task.done.wait(2)
    adapter.poll()
    return task


def test_load_from_other_cwd_and_poll_installs_only_on_owner(tmp_path, monkeypatch):
    paths = AppPaths.resolve(tmp_path)
    write_project(paths, "LoopbackDemo", sample_config())
    monkeypatch.chdir(tmp_path.parent)
    manager = ConfigManager(paths)
    adapter = ProjectConfigurationAdapter(manager, can_edit=lambda: True)
    task = adapter.load_project("LoopbackDemo")
    assert task.done.wait(2)
    assert manager.project_name is None
    adapter.poll()
    assert task.error is None
    assert adapter.current.name == "LoopbackDemo"
    assert adapter.current.settings.source_address == 0x0E80
    assert manager.project_name == "LoopbackDemo"
    adapter.close()
    adapter.shutdown()


@pytest.mark.parametrize("bad", [None, "{", "[]", '{"doip": {}}'])
def test_failed_load_keeps_previous_context(tmp_path, bad):
    paths = AppPaths.resolve(tmp_path)
    write_project(paths, "A", sample_config())
    if bad is not None:
        path = write_project(paths, "B", {})
        path.write_text(bad)
    manager = ConfigManager(paths)
    adapter = ProjectConfigurationAdapter(manager, can_edit=lambda: True)
    assert finish(adapter, adapter.load_project("A")).error is None
    previous = adapter.current
    assert finish(adapter, adapter.load_project("B")).error
    assert adapter.current is previous
    assert manager.project_name == "A"
    adapter.shutdown()


def test_save_preserves_unknown_fields_and_replace_failure_is_transactional(tmp_path, monkeypatch):
    paths = AppPaths.resolve(tmp_path)
    config = sample_config()
    config.update({"_comment_custom": "保留", "unknown": {"x": [3]}})
    path = write_project(paths, "A", config)
    manager = ConfigManager(paths)
    adapter = ProjectConfigurationAdapter(manager, can_edit=lambda: True)
    finish(adapter, adapter.load_project("A"))
    changed = replace(adapter.current.settings, target_port=12345)
    assert finish(adapter, adapter.save_project(changed)).error is None
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["unknown"] == {"x": [3]}
    assert saved["_comment_custom"] == "保留"
    assert manager.get("doip.target_port") == 12345
    old_file = path.read_bytes()
    previous = adapter.current
    def fail(*args):
        raise OSError("disk failed")
    monkeypatch.setattr("src.core.config_manager.os.replace", fail)
    failed = finish(adapter, adapter.save_project(replace(changed, target_port=23456)))
    assert "disk failed" in failed.error
    assert adapter.current is previous
    assert manager.get("doip.target_port") == 12345
    assert path.read_bytes() == old_file
    adapter.shutdown()


def test_busy_and_connection_guard_reject_reentry(tmp_path, monkeypatch):
    paths = AppPaths.resolve(tmp_path)
    write_project(paths, "A", sample_config())
    manager = ConfigManager(paths)
    allowed = [True]
    adapter = ProjectConfigurationAdapter(manager, can_edit=lambda: allowed[0])
    entered, release = threading.Event(), threading.Event()
    original = manager.prepare_project
    def slow(name):
        entered.set()
        assert release.wait(2)
        return original(name)
    monkeypatch.setattr(manager, "prepare_project", slow)
    task = adapter.load_project("A")
    assert entered.wait(1)
    assert adapter.busy
    rejected = adapter.load_project("A")
    assert rejected.done.is_set() and rejected.error
    release.set()
    finish(adapter, task)
    allowed[0] = False
    assert adapter.load_project("A").error
    assert adapter.save_project(adapter.current.settings).error
    adapter.shutdown()


def test_switch_does_not_inherit_and_close_discards_late_result(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    a = sample_config()
    a["only_a"] = True
    write_project(paths, "A", a)
    write_project(paths, "B", sample_config())
    manager = ConfigManager(paths)
    adapter = ProjectConfigurationAdapter(manager, can_edit=lambda: True)
    finish(adapter, adapter.load_project("A"))
    finish(adapter, adapter.load_project("B"))
    assert manager.get("only_a") is None
    task = adapter.load_project("A")
    adapter.close()
    adapter.shutdown()
    adapter.poll()
    assert task.done.is_set()
    assert manager.project_name == "B"


def test_repository_sample_configuration_is_valid(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    write_project(paths, "LoopbackDemo", sample_config())
    manager = ConfigManager(paths)
    adapter = ProjectConfigurationAdapter(manager, can_edit=lambda: True)
    task = finish(adapter, adapter.load_project("LoopbackDemo"))
    assert task.error is None
    assert task.result.settings.target_ip == "127.0.0.1"
    adapter.shutdown()
