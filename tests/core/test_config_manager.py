"""Project isolation, state preservation, and atomic JSON persistence."""

import json

import pytest

from src.core.app_paths import AppPaths
from src.core.config_manager import ConfigManager


def write_project(paths, name, data):
    config_file = paths.config_dir / name / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return config_file


def test_initialization_has_no_project_or_files(tmp_path):
    paths = AppPaths.resolve(tmp_path / "absent")
    manager = ConfigManager(paths)
    assert manager.project_name is None
    assert manager.config_path is None
    assert manager.get_transport() == "doip"
    assert manager.get_doip_config() == {}
    assert not paths.root.exists()
    with pytest.raises(RuntimeError, match="No project"):
        manager.save()


def test_project_switch_merges_fresh_basis_and_does_not_inherit_previous_project(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    global_data = {"uds": {"timeout": 99}, "global_only": {"value": 1}}
    manager = ConfigManager(paths, defaults={"uds": {"timeout": 10, "base": 4}}, global_config=global_data)
    global_data["global_only"]["value"] = 9
    write_project(paths, "A", {"transport": "docan", "uds": {"timeout": 20}, "project_only": 7})
    write_project(paths, "B", {"uds": {"other": 3}})
    manager.load_project("A")
    assert manager.get("uds") == {"timeout": 20, "base": 4}
    manager.set("transient", "A")
    manager.load_project("B")
    assert manager.project_name == "B"
    assert manager.get_transport() == "doip"
    assert manager.get("uds") == {"timeout": 99, "base": 4, "other": 3}
    assert manager.get("global_only.value") == 1
    assert manager.get("project_only") is None
    assert manager.get("transient") is None


@pytest.mark.parametrize("bad_content", ['{"broken":', "[]", "null", '{"number":NaN}'])
def test_load_failure_preserves_old_project(tmp_path, bad_content):
    paths = AppPaths.resolve(tmp_path)
    file_a = write_project(paths, "A", {"transport": "docan", "unchanged": [1]})
    file_b = write_project(paths, "B", {})
    file_b.write_text(bad_content, encoding="utf-8")
    manager = ConfigManager(paths)
    manager.load_project("A")
    with pytest.raises(ValueError):
        manager.load_project("B")
    assert manager.project_name == "A"
    assert manager.config_path == file_a
    assert manager.get("unchanged") == [1]
    assert manager.get_transport() == "docan"


def test_missing_project_keeps_old_state(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    write_project(paths, "A", {"existing": True})
    manager = ConfigManager(paths)
    manager.load_project("A")
    with pytest.raises(FileNotFoundError):
        manager.load_project("missing")
    assert manager.project_name == "A"
    assert manager.get("existing") is True


@pytest.mark.parametrize("name", ["", ".", "..", "../A", "A/B", "A\\B", "C:\\A", "C:A", "/A", " A", "A ", "A\x00B"])
def test_invalid_project_paths_rejected_without_file_access(tmp_path, name):
    manager = ConfigManager(AppPaths.resolve(tmp_path))
    with pytest.raises(ValueError, match="Project name"):
        manager.load_project(name)
    assert manager.project_name is None


def test_get_and_set_do_not_share_mutable_values(tmp_path):
    manager = ConfigManager(AppPaths.resolve(tmp_path))
    value = {"nested": [1]}
    manager.set("section", value)
    value["nested"].append(2)
    retrieved = manager.get("section")
    retrieved["nested"].append(3)
    assert manager.get("section.nested") == [1]
    fallback = []
    returned = manager.get("missing", fallback)
    returned.append("isolated")
    assert fallback == []
    manager.set("new.object.value", 4)
    assert manager.get("new.object.value") == 4
    with pytest.raises(ValueError, match="not an object"):
        manager.set("new.object.value.child", 5)
    assert manager.get("new.object.value") == 4


def test_save_preserves_unknown_and_comment_keys_and_unicode(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    original = {"_comment_transport": "项目说明", "unknown": {"list": [1, 2]}, "doip": {"custom": 3}}
    config_file = write_project(paths, "项目", original)
    manager = ConfigManager(paths)
    manager.load_project("项目")
    manager.set("doip.target_port", 13400)
    manager.save()
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        **original,
        "doip": {"custom": 3, "target_port": 13400},
    }
    assert "项目说明" in config_file.read_text(encoding="utf-8")
    assert not list(config_file.parent.glob("*.tmp"))


def test_replace_failure_keeps_original_and_removes_temporary_file(tmp_path, monkeypatch):
    paths = AppPaths.resolve(tmp_path)
    config_file = write_project(paths, "A", {"old": True})
    original_bytes = config_file.read_bytes()
    manager = ConfigManager(paths)
    manager.load_project("A")
    manager.set("old", False)

    def denied_replace(*args):
        raise PermissionError("replacement denied")

    monkeypatch.setattr("src.core.config_manager.os.replace", denied_replace)
    with pytest.raises(PermissionError, match="replacement denied"):
        manager.save()
    assert config_file.read_bytes() == original_bytes
    assert manager.get("old") is False
    assert not list(config_file.parent.glob("*.tmp"))


def test_flush_failure_keeps_original_and_removes_temporary_file(tmp_path, monkeypatch):
    paths = AppPaths.resolve(tmp_path)
    config_file = write_project(paths, "A", {"old": True})
    original_bytes = config_file.read_bytes()
    manager = ConfigManager(paths)
    manager.load_project("A")

    def denied_fsync(*args):
        raise OSError("disk flush failed")

    monkeypatch.setattr("src.core.config_manager.os.fsync", denied_fsync)
    with pytest.raises(OSError, match="disk flush failed"):
        manager.save()
    assert config_file.read_bytes() == original_bytes
    assert not list(config_file.parent.glob("*.tmp"))


@pytest.mark.parametrize("transport,expected", [("doip", "doip"), ("docan", "docan"), ("invalid", "doip"), (None, "doip")])
def test_transport_rule_is_field_specific(tmp_path, transport, expected):
    manager = ConfigManager(AppPaths.resolve(tmp_path))
    manager.set("transport", transport)
    assert manager.get_transport() == expected


def test_section_readers_reject_wrong_shape_instead_of_hiding_it(tmp_path):
    manager = ConfigManager(AppPaths.resolve(tmp_path))
    manager.set("docan", {"req_id": 2016})
    manager.set("flash", {"custom": True})
    assert manager.get_can_diag_config() == {"req_id": 2016}
    assert manager.get_flash_config() == {"custom": True}
    manager.set("doip", ["invalid"])
    with pytest.raises(ValueError, match="section"):
        manager.get_doip_config()


def test_save_does_not_turn_inherited_basis_values_into_project_overrides(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    original = {"_comment_custom": "保留", "custom": {"unknown": True}}
    config_file = write_project(paths, "A", original)
    manager = ConfigManager(
        paths,
        defaults={"uds": {"timeout": 10}, "default_only": [1]},
        global_config={"uds": {"timeout": 20}, "global_only": "inherited"},
    )
    manager.load_project("A")
    assert manager.get("uds.timeout") == 20
    manager.save()
    assert json.loads(config_file.read_text(encoding="utf-8")) == original

    changed_basis = ConfigManager(paths, global_config={"uds": {"timeout": 30}})
    changed_basis.load_project("A")
    assert changed_basis.get("uds.timeout") == 30


def test_save_preserves_original_and_explicit_overrides_equal_to_basis(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    config_file = write_project(paths, "A", {"uds": {"timeout": 20}})
    manager = ConfigManager(paths, global_config={"uds": {"timeout": 20, "interval": 5}})
    manager.load_project("A")
    manager.set("uds.interval", 5)
    manager.save()
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "uds": {"timeout": 20, "interval": 5},
    }
    changed_basis = ConfigManager(paths, global_config={"uds": {"timeout": 30, "interval": 8}})
    changed_basis.load_project("A")
    assert changed_basis.get("uds") == {"timeout": 20, "interval": 5}


def test_set_under_inherited_parent_writes_only_explicitly_modified_child(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    config_file = write_project(paths, "A", {"_comment_doip": "原说明"})
    manager = ConfigManager(paths, global_config={
        "doip": {"target_port": 13400, "nested": {"inherited": [1], "changed": 2}},
    })
    manager.load_project("A")
    manager.set("doip.nested.changed", 3)
    assert manager.get("doip") == {
        "target_port": 13400, "nested": {"inherited": [1], "changed": 3},
    }
    manager.save()
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "_comment_doip": "原说明", "doip": {"nested": {"changed": 3}},
    }


def test_failed_load_keeps_pending_project_edits_for_later_save(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    config_file = write_project(paths, "A", {"unknown": [1]})
    manager = ConfigManager(paths, defaults={"inherited": True})
    manager.load_project("A")
    manager.set("explicit", 2)
    with pytest.raises(FileNotFoundError):
        manager.load_project("missing")
    manager.save()
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "unknown": [1], "explicit": 2,
    }


def test_set_below_nonobject_inherited_parent_is_transactional(tmp_path):
    paths = AppPaths.resolve(tmp_path)
    config_file = write_project(paths, "A", {"unknown": [1]})
    manager = ConfigManager(paths, global_config={"doip": {"target_port": 13400}})
    manager.load_project("A")
    with pytest.raises(ValueError, match="not an object"):
        manager.set("doip.target_port.invalid", 3)
    manager.save()
    assert manager.get("doip.target_port") == 13400
    assert json.loads(config_file.read_text(encoding="utf-8")) == {"unknown": [1]}
