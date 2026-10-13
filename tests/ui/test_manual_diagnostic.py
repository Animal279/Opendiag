from dataclasses import replace
import json
import threading

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from src.ports.model_types import SessionState
from src.ui.config_dialogs import DiagnosticConnectionDialog
from tests.integration.test_manual_diagnostic_workflow import make_window, load_project, RA
from tests.fixtures.fake_doip_server import FakeDoIPServer
from src.ui.command_editor import CommandEditor
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QFileDialog
from src.ports.projects import ProjectTask
from src.ports.events import LogEvent
from src.ui.main_window import CommunicationPanel
from src.adapters.qt_event_bus import QtDomainEventBus


@pytest.mark.parametrize("response,reason", [(bytes.fromhex("02fd0006000000090e8011100000000000"), "0x00"), (None, "超时")])
def test_rejection_and_timeout_recover_configuration_and_disable_send(qtbot, tmp_path, response, reason):
    with FakeDoIPServer() as server:
        if response is not None: server.queue_response(response)
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            load_project(qtbot, container, window)
            window.connect_button.click()
            assert not window.command_editor.send_button.isEnabled()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.FAILED)
            assert reason in window.connection_label.toolTip()
            assert window.settings_button.isEnabled()
            assert not window.command_editor.send_button.isEnabled()
        finally:
            window.close(); container.shutdown()


def test_real_configuration_cancel_apply_save_and_locked_accept(qtbot, tmp_path):
    with FakeDoIPServer() as server:
        server.queue_response(RA)
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            load_project(qtbot, container, window)
            initial = window.diagnostic_controller.settings
            path = container.config_manager.config_path
            old_file = path.read_bytes()
            window.show_connection_settings()
            dialog = window.findChildren(DiagnosticConnectionDialog)[-1]
            dialog.target.setText("0x2222")
            dialog.reject()
            assert window.diagnostic_controller.settings == initial
            window.show_connection_settings()
            dialog = window.findChildren(DiagnosticConnectionDialog)[-1]
            dialog.target.setText("0x2222")
            dialog.accept()
            assert window.diagnostic_controller.settings.target_address == 0x2222
            assert path.read_bytes() == old_file
            window.show_connection_settings()
            dialog = window.findChildren(DiagnosticConnectionDialog)[-1]
            dialog.target.setText("0x1110")
            dialog.save_button.click()
            qtbot.waitUntil(lambda: not container.projects.busy)
            assert json.loads(path.read_text(encoding="utf-8"))["doip"]["target_address"] == 0x1110
            window.show_connection_settings()
            locked = window.findChildren(DiagnosticConnectionDialog)[-1]
            window.connect_button.click()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.READY)
            locked.target.setText("0x3333")
            locked.accept()
            assert locked.result() != QDialog.DialogCode.Accepted
            assert window.diagnostic_controller.settings.target_address == 0x1110
            assert locked.error_label.isVisible()
        finally:
            window.close(); container.shutdown()


def test_shortcut_and_keep_alive_only_after_activation(qtbot, tmp_path):
    with FakeDoIPServer() as server:
        server.queue_response(RA)
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            load_project(qtbot, container, window)
            assert not window.command_editor.keep_alive_button.isEnabled()
            window.diagnostic_controller.settings = replace(window.diagnostic_controller.settings, tester_present_interval_ms=10)
            window.connect_button.click()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.READY)
            window.command_editor.command_input.setText("10 03")
            window.activateWindow()
            window.command_editor.command_input.setFocus()
            qtbot.waitUntil(window.command_editor.command_input.hasFocus)
            qtbot.keyClick(window.command_editor.command_input, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
            qtbot.waitUntil(lambda: len(server.received) >= 2)
            window.command_editor.keep_alive_button.setChecked(True)
            qtbot.waitUntil(lambda: any(frame.hex() == "02fd8001000000060e80e4003e80" for frame in server.received))
        finally:
            window.close(); container.shutdown()
        assert container.manual_diagnostic.is_quiescent()


def test_invalid_project_load_keeps_previous_project_and_inputs(qtbot, tmp_path):
    with FakeDoIPServer() as server:
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            load_project(qtbot, container, window)
            old = window.diagnostic_controller.settings
            window.command_editor.command_input.setText("22 F1 90")
            window.diagnostic_controller.load_project("missing")
            qtbot.waitUntil(lambda: not container.projects.busy)
            assert window.diagnostic_controller.settings == old
            assert window.command_editor.command_input.text() == "22 F1 90"
            assert window.connect_button.isEnabled()
            assert any(e.level == "ERROR" for e in window.communication.records)
        finally:
            window.close(); container.shutdown()


def test_move_preserves_single_selection_while_control_is_held(qtbot):
    editor = CommandEditor(demo=True)
    qtbot.addWidget(editor)
    editor.show()
    editor.activateWindow()
    editor.command_input.setFocus()
    qtbot.waitUntil(editor.command_input.hasFocus)
    editor.table.selectionModel().select(editor.table.model().index(2, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    qtbot.keyClick(editor.command_input, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    try:
        editor.move_up()
        assert [index.row() for index in editor.table.selectionModel().selectedRows()] == [1]
        editor.move_down()
        assert [index.row() for index in editor.table.selectionModel().selectedRows()] == [2]
    finally:
        qtbot.keyClick(editor.command_input, Qt.Key.Key_Escape)


def test_failed_save_retains_project_dialog_and_user_input(qtbot, tmp_path, monkeypatch):
    with FakeDoIPServer() as server:
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            load_project(qtbot, container, window)
            original = container.projects.current
            window.show_connection_settings()
            dialog = window.findChildren(DiagnosticConnectionDialog)[-1]
            dialog.target.setText("0x2222")
            def denied(*args): raise OSError("injected save failure")
            monkeypatch.setattr("src.core.config_manager.os.replace", denied)
            dialog.save_button.click()
            qtbot.waitUntil(lambda: dialog.error_label.isVisible())
            assert "save failure" in dialog.error_label.text()
            assert dialog.target.text() == "0x2222"
            assert container.projects.current is original
            assert dialog.save_button.isEnabled()
        finally:
            window.close(); container.shutdown()


def test_cancel_save_dialog_during_worker_does_not_use_destroyed_qobject(qtbot, tmp_path, monkeypatch):
    from src.core.config_manager import ConfigManager
    from shiboken6 import isValid
    with FakeDoIPServer() as server:
        container, window = make_window(qtbot, tmp_path, server.port)
        entered, release = threading.Event(), threading.Event()
        original = ConfigManager.save
        def slow(manager):
            entered.set()
            assert release.wait(2)
            original(manager)
        try:
            load_project(qtbot, container, window)
            monkeypatch.setattr(ConfigManager, "save", slow)
            window.show_connection_settings()
            dialog = window.findChildren(DiagnosticConnectionDialog)[-1]
            dialog.save_button.click()
            assert entered.wait(1)
            dialog.reject()
            qtbot.waitUntil(lambda: not isValid(dialog))
            release.set()
            qtbot.waitUntil(lambda: window.diagnostic_controller._task is None)
            assert container.projects.current is not None
        finally:
            release.set()
            window.close(); container.shutdown()


def test_log_export_stays_locked_while_new_records_arrive(qtbot, tmp_path):
    class PendingExport:
        def __init__(self):
            self.calls = []
            self.task = ProjectTask()

        def export(self, events, path):
            self.calls.append((events, path))
            return self.task

    port, bus = PendingExport(), QtDomainEventBus()
    notifications = []
    bus.subscribe(LogEvent, notifications.append)
    panel = CommunicationPanel(log_export=port, event_bus=bus)
    qtbot.addWidget(panel)
    try:
        initial = LogEvent("RX", b"\x50\x03", "initial")
        panel.append(initial)
        panel._export_selected(str(tmp_path / "first.txt"))
        panel.append(LogEvent("RX", b"\x7F\x10\x78", "during export"))
        assert not panel.save_button.isEnabled()
        panel.export_logs()
        assert panel.findChildren(QFileDialog) == []
        panel._export_selected(str(tmp_path / "second.txt"))
        assert len(port.calls) == 1 and port.calls[0][0] == (initial,)
        assert any("正在导出" in event.description for event in notifications)
        port.task.result = tmp_path / "first.txt"
        port.task.done.set()
        panel.poll_export()
        assert panel.save_button.isEnabled()
        assert any("first.txt" in event.description for event in notifications)
    finally:
        bus.close()
