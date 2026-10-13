from pathlib import Path

from .events import LogEvent
from .projects import ProjectTask


class LogExportPort:
    def export(self, events: tuple[LogEvent, ...], path: Path) -> ProjectTask[Path]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
