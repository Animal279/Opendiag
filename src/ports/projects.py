from dataclasses import dataclass, field
from threading import Event
from typing import Generic, TypeVar

from .model_types import DoIPSettings

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    name: str
    settings: DoIPSettings


@dataclass(slots=True)
class ProjectTask(Generic[T]):
    """Worker writes result/error before done.set; poll then installs the result."""
    done: Event = field(default_factory=Event)
    result: T | None = None
    error: str | None = None


class ProjectPort:
    def list_projects(self) -> ProjectTask[tuple[str, ...]]:
        raise NotImplementedError

    def load_project(self, name: str) -> ProjectTask[ProjectSnapshot]:
        raise NotImplementedError

    def save_project(self, settings: DoIPSettings) -> ProjectTask[ProjectSnapshot]:
        raise NotImplementedError

    def poll(self) -> None:
        raise NotImplementedError

    @property
    def busy(self) -> bool:
        raise NotImplementedError

    @property
    def current(self) -> ProjectSnapshot | None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
