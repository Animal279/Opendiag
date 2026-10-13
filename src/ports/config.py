"""Known configuration access boundary; local provisional method annotations."""

from typing import Any


class ConfigPort:
    """Ordinary base contract supporting duck-typed file adapters."""

    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def save(self) -> None:
        raise NotImplementedError

    def get_transport(self) -> str:
        raise NotImplementedError

    def get_doip_config(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_can_diag_config(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_flash_config(self) -> dict[str, Any]:
        raise NotImplementedError
