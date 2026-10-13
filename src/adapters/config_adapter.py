"""Thin ConfigPort adapter; file execution remains the caller's responsibility."""

from __future__ import annotations

from typing import Any

from src.core.config_manager import ConfigManager
from src.ports.config import ConfigPort


class ConfigAdapter(ConfigPort):
    def __init__(self, manager: ConfigManager) -> None:
        self._manager = manager

    def get(self, key: str, default: Any = None) -> Any:
        return self._manager.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._manager.set(key, value)

    def save(self) -> None:
        self._manager.save()

    def get_transport(self) -> str:
        return self._manager.get_transport()

    def get_doip_config(self) -> dict[str, Any]:
        return self._manager.get_doip_config()

    def get_can_diag_config(self) -> dict[str, Any]:
        return self._manager.get_can_diag_config()

    def get_flash_config(self) -> dict[str, Any]:
        return self._manager.get_flash_config()
