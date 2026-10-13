"""Synchronous, project-main JSON configuration infrastructure.

This does not load device overrides, plugins, session state or secret defaults.
The caller owns execution and serializes access, placing file IO in a worker
when invoked by the UI. Returned and supplied values are copied, never shared.
"""

from __future__ import annotations

import json
import ntpath
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .app_paths import AppPaths


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite JSON value is not supported: {value}")


@dataclass(frozen=True, slots=True)
class PreparedProject:
    name: str
    path: Path
    data: dict[str, Any]


class ConfigManager:
    """Main-config effective view with project-only atomic file replacement.

    No missing global schema or device settings are invented. Optional basis
    dictionaries are supplied by the caller and isolated from later mutation.
    Dot-separated get/set paths are a local API choice for nested JSON objects.
    Inherited basis values are never written as project overrides; original
    project keys and explicit set calls are retained even if equal to the basis.
    """

    def __init__(
        self,
        app_paths: AppPaths,
        *,
        defaults: dict[str, Any] | None = None,
        global_config: dict[str, Any] | None = None,
    ) -> None:
        for label, value in (("defaults", defaults), ("global_config", global_config)):
            if value is not None and not isinstance(value, dict):
                raise TypeError(f"{label} must be a JSON object")
        self.app_paths = app_paths
        self._basis = _merge(defaults or {}, global_config or {})
        self._project_data: dict[str, Any] = {}
        self._data = deepcopy(self._basis)
        self._project_name: str | None = None
        self._config_path: Path | None = None

    @property
    def project_name(self) -> str | None:
        return self._project_name

    @property
    def config_path(self) -> Path | None:
        return self._config_path

    @staticmethod
    def _keys(key: str) -> list[str]:
        if not isinstance(key, str) or not key or any(not part for part in key.split(".")):
            raise ValueError("Configuration key must be a non-empty dot-separated path")
        return key.split(".")

    def get(self, key: str, default: Any = None) -> Any:
        value: Any = self._data
        for part in self._keys(key):
            if not isinstance(value, dict) or part not in value:
                return deepcopy(default)
            value = value[part]
        return deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        parts = self._keys(key)
        updated = deepcopy(self._project_data)
        target = updated
        effective = self._data
        for part in parts[:-1]:
            if part in effective and not isinstance(effective[part], dict):
                raise ValueError(f"Configuration parent is not an object: {part}")
            effective = effective.get(part, {})
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = deepcopy(value)
        data = _merge(self._basis, updated)
        self._project_data = updated
        self._data = data

    def load_project(self, project_name: str) -> None:
        """Load config/<name>/config.json; any error leaves current state intact."""
        self.adopt_project(self.prepare_project(project_name))

    def prepare_project(self, project_name: str) -> PreparedProject:
        """Read only; installation belongs to the caller's owner thread."""
        if (
            not isinstance(project_name, str)
            or not project_name
            or project_name != project_name.strip()
            or project_name in {".", ".."}
            or any(char in project_name for char in '/\\:\x00')
            or ntpath.splitdrive(project_name)[0]
        ):
            raise ValueError("Project name must be a single relative directory name")
        config_root = self.app_paths.config_dir.resolve()
        config_path = (config_root / project_name / "config.json").resolve()
        if not config_path.is_relative_to(config_root):
            raise ValueError("Project configuration must stay within the config directory")
        with config_path.open("r", encoding="utf-8-sig") as config_file:
            project = json.load(config_file, parse_constant=_reject_nonfinite)
        if not isinstance(project, dict):
            raise ValueError("Project main configuration must be a JSON object")
        return PreparedProject(project_name, config_path, project)

    def adopt_project(self, prepared: PreparedProject) -> None:
        data = _merge(self._basis, prepared.data)
        self._project_data = deepcopy(prepared.data)
        self._data = data
        self._project_name = prepared.name
        self._config_path = prepared.path

    def candidate_for(self, prepared: PreparedProject) -> ConfigManager:
        candidate = ConfigManager(self.app_paths, defaults=self._basis)
        candidate.adopt_project(prepared)
        return candidate

    def snapshot_project(self) -> PreparedProject:
        if self._config_path is None or self._project_name is None:
            raise RuntimeError("No project main configuration has been loaded")
        return PreparedProject(self._project_name, self._config_path, deepcopy(self._project_data))

    def save(self) -> None:
        """Save original project keys plus explicit edits, preserving unknown keys.

        Serializing and writing a temporary file completes before replacement.
        Failed writes keep the previous file, and temporary files are removed.
        This is not a multi-instance locking or complete project-bundle writer.
        """
        if self._config_path is None:
            raise RuntimeError("No project main configuration has been loaded")
        content = json.dumps(self._project_data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self._config_path.parent,
                prefix=f".{self._config_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self._config_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def get_transport(self) -> str:
        transport = self.get("transport")
        return "docan" if transport == "docan" else "doip"

    def _section(self, key: str) -> dict[str, Any]:
        value = self.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(f"Configuration section must be an object: {key}")
        return value

    def get_doip_config(self) -> dict[str, Any]:
        return self._section("doip")

    def get_can_diag_config(self) -> dict[str, Any]:
        return self._section("docan")

    def get_flash_config(self) -> dict[str, Any]:
        return self._section("flash")
