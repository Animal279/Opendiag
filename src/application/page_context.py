"""Minimal locally defined P1 context; original full PageContext is pending."""

from dataclasses import dataclass
from pathlib import Path

from src.ports.config import ConfigPort
from src.ports.event_bus import EventBusPort
from src.ports.projects import ProjectPort
from src.ports.manual_diagnostic import ManualDiagnosticPort
from src.ports.log_export import LogExportPort


@dataclass(frozen=True)
class PageContext:
    config: ConfigPort
    event_bus: EventBusPort
    application_root: Path
    version: str
    projects: ProjectPort | None = None
    manual_diagnostic: ManualDiagnosticPort | None = None
    log_export: LogExportPort | None = None
