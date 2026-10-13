"""Application-root precedence and launch-directory independence."""

import sys
from pathlib import Path

import pytest

from src.core import app_paths
from src.core.app_paths import AppPaths


def test_explicit_root_overrides_environment_without_creating_directories(tmp_path, monkeypatch):
    root = tmp_path / "应用目录"
    monkeypatch.setenv("DOIP_APP_DIR", str(tmp_path / "environment"))
    paths = AppPaths.resolve(root)
    assert paths.root == root
    assert [paths.config_dir, paths.testcase_dir, paths.logs_dir, paths.docs_dir] == [
        root / name for name in ("config", "testcase", "logs", "docs")
    ]
    assert not root.exists()


def test_environment_root_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    root = tmp_path / "application"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("DOIP_APP_DIR", str(root))
    monkeypatch.chdir(elsewhere)
    assert AppPaths.resolve().root == root


def test_frozen_executable_root(tmp_path, monkeypatch):
    monkeypatch.delenv("DOIP_APP_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "release" / "OpenDiag.exe"))
    assert AppPaths.resolve().root == tmp_path / "release"


def test_source_root_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("DOIP_APP_DIR", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    assert AppPaths.resolve().root == Path(app_paths.__file__).resolve().parents[2]


@pytest.mark.parametrize("from_environment", [False, True])
def test_relative_root_is_rejected(monkeypatch, from_environment):
    if from_environment:
        monkeypatch.setenv("DOIP_APP_DIR", "relative-root")
        root = None
    else:
        root = "relative-root"
    with pytest.raises(ValueError, match="absolute"):
        AppPaths.resolve(root)
