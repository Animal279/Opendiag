"""Composition root. Startup constructs services without opening sockets/SDKs."""

import logging
from pathlib import Path

from src.adapters.config_adapter import ConfigAdapter
from src.adapters.file_logging import BackgroundFileLogging
from src.adapters.qt_event_bus import QtDomainEventBus
from src.adapters.doip_adapter import DoIPAdapter
from src.adapters.project_configuration import ProjectConfigurationAdapter
from src.adapters.log_export import LogExportAdapter
from src.application.manual_diagnostic_service import ManualDiagnosticService
from src.application.page_context import PageContext
from src.core.app_paths import AppPaths
from src.core.config_manager import ConfigManager
from src.core.doip_protocol import DoIPProtocol
from src.ports.events import LogEvent, ErrorEvent
from src.ports.model_types import SessionState
from src.version import __version__


class AppContainer:
    def __init__(self, app_root: str | Path | None = None):
        self.paths = AppPaths.resolve(app_root)
        self.config_manager = ConfigManager(self.paths)
        self.config = ConfigAdapter(self.config_manager)
        self.event_bus = QtDomainEventBus()
        self.protocol = DoIPProtocol()
        self.doip_adapter = DoIPAdapter(self.protocol, self.event_bus)
        self.manual_diagnostic = ManualDiagnosticService(self.doip_adapter, self.doip_adapter, self.event_bus)
        self.projects = ProjectConfigurationAdapter(self.config_manager, can_edit=self._can_edit_project)
        self.log_export = LogExportAdapter()
        self.file_logging = BackgroundFileLogging(self.paths.logs_dir, on_error=self._logging_error)
        self.event_bus.subscribe(LogEvent, self._record_event)
        self.page_context = PageContext(
            self.config, self.event_bus, self.paths.root, __version__, self.projects, self.manual_diagnostic, self.log_export
        )
        self._closed = False

    def _record_event(self, event: LogEvent) -> None:
        level = {"DEBUG": logging.DEBUG, "INFO": logging.INFO,
                 "WARN": logging.WARNING, "ERROR": logging.ERROR}.get(event.level, logging.INFO)
        logger = self.file_logging.logger
        if logger.isEnabledFor(level):
            record = logger.makeRecord(logger.name, level, "", 0, "[%s] %s", (event.level, event.description), None, extra={"wire_data": event.data})
            record.created = event.timestamp
            record.msecs = (event.timestamp % 1) * 1000
            logger.handle(record)

    def _logging_error(self, message):
        # Safe from a file worker: bus.publish queues onto its bound QObject receiver.
        self.event_bus.publish(ErrorEvent(message, "file-logging"))

    def _can_edit_project(self):
        return self.manual_diagnostic.snapshot.state in (SessionState.DISCONNECTED, SessionState.FAILED) and self.manual_diagnostic.is_quiescent()

    def create_window(self, *, ui_demo: bool = False):
        from src.ui.main_window import MainWindow

        return MainWindow(self.page_context, ui_demo=ui_demo)

    def shutdown(self) -> None:
        """Call on owner thread after UI closes; releases infrastructure only."""
        if self._closed:
            return
        self._closed = True
        errors = []
        for action in (self.manual_diagnostic.close, self.projects.close,
                       self.manual_diagnostic.shutdown, self.doip_adapter.shutdown,
                       self.projects.shutdown, self.log_export.shutdown,
                       self.event_bus.close, self.file_logging.close):
            try:
                action()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError("资源清理失败：" + "; ".join(str(exc) for exc in errors))
