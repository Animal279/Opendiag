"""Exercise local UI previews and their boundaries without an ECU or assets."""

from collections import deque
from copy import deepcopy
from datetime import datetime
import socket

import pytest
from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtWidgets import QApplication, QDialog

from src.application.app_container import AppContainer
from src.ports.events import ConnectionEvent, DataSentEvent, LogEvent
from src.ui.command_editor import CommandEditor, TextTransferDialog
from src.ui.config_dialogs import ConnectionDialog, HardwareDialog
from src.ui.main_window import CommunicationPanel, PAGE_DEFINITIONS


@pytest.fixture
def window_factory(qtbot, tmp_path):
    created = []

    def make(*, demo=False):
        root = tmp_path / f"window-{len(created)}"
        root.mkdir()
        container = AppContainer(root)
        window = container.create_window(ui_demo=demo)
        qtbot.addWidget(window)
        created.append((container, window))
        return container, window

    yield make
    for container, window in reversed(created):
        window.close()
        container.shutdown()
        assert not container.file_logging.thread.is_alive()


def _payloads(editor):
    return tuple(
        editor.table.item(row, 2).data(Qt.ItemDataRole.UserRole)
        for row in range(editor.table.rowCount())
    )


def _latest_dialog(parent, dialog_type):
    return parent.findChildren(dialog_type)[-1]


def test_default_startup_has_no_sample_commands_or_preview_connection(window_factory, monkeypatch):
    def unexpected_socket(*_args, **_kwargs):
        raise AssertionError("UI startup and local preview must not create sockets")

    monkeypatch.setattr(socket, "socket", unexpected_socket)
    container, window = window_factory()
    assert not window.ui_demo
    assert not window._preview_connected
    assert window.command_editor.table.rowCount() == 0
    assert window.command_editor.command_input.text() == ""
    assert not window.connect_button.isEnabled()
    assert not window.command_editor.send_button.isEnabled()
    assert not window.command_editor.batch_button.isEnabled()
    assert not window.communication.records
    window.toggle_preview_connection()
    window.command_editor.set_preview_connection(True)
    assert not window._preview_connected
    assert not window.command_editor.send_button.isEnabled()
    assert not (container.paths.root / "config").exists()


def test_explicit_demo_connection_and_send_publish_only_local_log_events(window_factory, monkeypatch):
    monkeypatch.setattr(
        socket, "socket",
        lambda *_args, **_kwargs: pytest.fail("UI demonstration created a socket"),
    )
    container, window = window_factory(demo=True)
    logs, connections, sent = [], [], []
    container.event_bus.subscribe(LogEvent, logs.append)
    container.event_bus.subscribe(ConnectionEvent, connections.append)
    container.event_bus.subscribe(DataSentEvent, sent.append)
    assert window.command_editor.table.rowCount() > 0
    assert not window.command_editor.send_button.isEnabled()
    window.connect_button.click()
    assert window._preview_connected
    assert window.command_editor.send_button.isEnabled()
    window.command_editor.command_input.setText("10 03")
    window.command_editor.addressing_button.setChecked(True)
    window.command_editor.send_button.click()
    requests = [event for event in logs if event.data is not None]
    assert len(requests) == 1
    assert requests[0].data == b"\x10\x03"
    assert requests[0].level == "INFO"
    assert not connections
    assert not sent
    window.connect_button.click()
    assert not window._preview_connected
    assert not window.command_editor.send_button.isEnabled()
    assert not (container.paths.root / "config").exists()


@pytest.mark.parametrize("invalid", ("", "GG", "1", "0x10", "10 03 0"))
def test_invalid_hex_addition_preserves_the_command_list(qtbot, invalid):
    editor = CommandEditor()
    qtbot.addWidget(editor)
    editor.add_payloads((b"\x10\x03",))
    before = _payloads(editor)
    editor.command_input.setText(invalid)
    editor.add_button.click()
    assert _payloads(editor) == before
    assert editor.error_label.text()


def test_invalid_edit_rolls_back_bytes_and_valid_edit_resets_preview_status(qtbot):
    editor = CommandEditor(demo=True)
    qtbot.addWidget(editor)
    editor.clear_commands()
    editor.add_payloads((b"\x10\x03",))
    editor.set_preview_connection(True)
    editor.send_checked()
    status = editor.table.item(0, 5)
    previewed_status = status.text()
    command = editor.table.item(0, 2)
    original_text = command.text()
    command.setText("XYZ")
    assert command.data(Qt.ItemDataRole.UserRole) == b"\x10\x03"
    assert command.text() == original_text
    assert status.text() == previewed_status
    assert editor.error_label.text()
    command.setText("3e80")
    assert command.data(Qt.ItemDataRole.UserRole) == b"\x3e\x80"
    assert command.text() == "3E 80"
    assert status.text() != previewed_status
    assert not editor.error_label.text()


def test_ordering_deletion_and_batch_checkboxes_keep_row_metadata_together(qtbot):
    editor = CommandEditor(demo=True)
    qtbot.addWidget(editor)
    editor.clear_commands()
    data = (b"\x10\x01", b"\x10\x02", b"\x10\x03")
    editor.add_payloads(data)
    editor.set_preview_connection(True)
    editor.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    editor.table.item(2, 4).setCheckState(Qt.CheckState.Checked)
    editor.table.selectRow(2)
    editor.move_up()
    assert _payloads(editor) == (data[0], data[2], data[1])
    assert editor.table.item(1, 4).checkState() == Qt.CheckState.Checked
    assert editor.table.item(2, 0).checkState() == Qt.CheckState.Unchecked
    editor.move_down()
    assert _payloads(editor) == data
    editor.table.clearSelection()
    requests = []
    editor.preview_requested.connect(lambda payload, functional: requests.append((payload, functional)))
    editor.batch_button.click()
    assert requests == [(data[0], False), (data[2], True)]
    assert editor.table.item(1, 5).text() != editor.table.item(0, 5).text()
    for row in range(editor.table.rowCount()):
        editor.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
    assert not editor.batch_button.isEnabled()
    editor.select_all()
    assert editor.batch_button.isEnabled()
    editor.table.selectRow(1)
    editor.remove_selected()
    assert _payloads(editor) == (data[0], data[2])
    assert [editor.table.item(row, 1).text() for row in range(2)] == ["1", "2"]
    editor.table.clearSelection()
    editor.remove_selected()
    assert not _payloads(editor)
    assert not editor.batch_button.isEnabled()


@pytest.mark.parametrize("enter_key", (Qt.Key.Key_Return, Qt.Key.Key_Enter))
def test_shift_enter_adds_and_ctrl_enter_previews_from_input_focus(qtbot, enter_key):
    editor = CommandEditor(demo=True)
    qtbot.addWidget(editor)
    editor.clear_commands()
    editor.set_preview_connection(True)
    editor.show()
    editor.activateWindow()
    editor.command_input.setFocus()
    qtbot.waitUntil(editor.command_input.hasFocus)
    editor.command_input.setText("10 03")
    qtbot.keyClick(editor.command_input, enter_key, modifier=Qt.KeyboardModifier.ShiftModifier)
    qtbot.waitUntil(lambda: editor.table.rowCount() == 1)
    assert _payloads(editor) == (b"\x10\x03",)
    with qtbot.waitSignal(editor.preview_requested) as signal:
        qtbot.keyClick(editor.command_input, enter_key, modifier=Qt.KeyboardModifier.ControlModifier)
    assert signal.args == [b"\x10\x03", False]
    assert editor.table.rowCount() == 1


def test_text_import_validates_every_line_before_atomic_append(qtbot):
    editor = CommandEditor()
    qtbot.addWidget(editor)
    editor.add_payloads((b"\x10\x01",))
    editor.import_commands()
    dialog = _latest_dialog(editor, TextTransferDialog)
    imported = []
    dialog.imported.connect(imported.append)
    dialog.editor.setPlainText("10 03\n\nGG\n3E 80")
    dialog._transfer()
    assert _payloads(editor) == (b"\x10\x01",)
    assert not imported
    assert "3" in dialog.error_label.text()
    assert dialog.isVisible()
    dialog.editor.setPlainText("10 03\n\n3e80")
    dialog._transfer()
    assert imported == [(b"\x10\x03", b"\x3e\x80")]
    assert _payloads(editor) == (b"\x10\x01", b"\x10\x03", b"\x3e\x80")


def test_communication_debug_filter_and_eviction_keep_visible_rows_consistent(qtbot):
    panel = CommunicationPanel()
    qtbot.addWidget(panel)
    assert panel.records.maxlen == 5000
    panel.records = deque(maxlen=3)
    for level in ("DEBUG", "INFO", "WARN"):
        panel.append(LogEvent(level=level, data=None, description=level))
    assert panel.table.rowCount() == 2
    assert panel.application_log.toPlainText().splitlines() == ["[WARN] WARN"]
    panel.debug_checkbox.setChecked(True)
    assert panel.table.rowCount() == 3
    panel.debug_checkbox.setChecked(False)
    panel.append(LogEvent(level="ERROR", data=None, description="ERROR"))
    assert [panel.table.item(row, 1).text() for row in range(3)] == ["INFO", "WARN", "ERROR"]
    panel.append(LogEvent(level="DEBUG", data=None, description="latest debug"))
    assert [panel.table.item(row, 1).text() for row in range(2)] == ["WARN", "ERROR"]
    panel.debug_checkbox.setChecked(True)
    assert [panel.table.item(row, 1).text() for row in range(3)] == ["WARN", "ERROR", "DEBUG"]
    assert panel.application_log.toPlainText().splitlines() == ["[WARN] WARN", "[ERROR] ERROR"]
    panel.clear_button.click()
    assert not panel.records
    assert panel.table.rowCount() == 0
    assert panel.application_log.toPlainText() == ""
    assert not panel.copy_button.isEnabled()


def test_communication_limit_evicts_the_oldest_after_5000_events(qtbot):
    panel = CommunicationPanel()
    qtbot.addWidget(panel)
    for index in range(5001):
        panel.append(LogEvent(level="INFO", data=None, description=f"entry {index}"))
    assert len(panel.records) == panel.table.rowCount() == 5000
    assert panel.records[0].description == panel.table.item(0, 3).text() == "entry 1"
    assert panel.records[-1].description == panel.table.item(4999, 3).text() == "entry 5000"


def test_large_log_payload_copy_and_export_preserve_bytes_and_source_timestamp(qtbot):
    panel = CommunicationPanel()
    qtbot.addWidget(panel)
    data = bytes(range(256)) * 4096
    timestamp = 1600000000.123456
    event = LogEvent(level="RX", data=data, description="source time", timestamp=timestamp)
    panel.append(event)
    assert panel.records[0] is event
    assert panel.table.item(0, 0).text().endswith(".123")
    item = panel.table.item(0, 2)
    assert len(item.text()) == 514
    assert item.data(Qt.ItemDataRole.UserRole) == data
    panel.table.selectRow(0)
    panel.copy_button.click()
    assert QApplication.clipboard().text() == data.hex(" ").upper()
    panel.export_logs()
    dialog = _latest_dialog(panel, TextTransferDialog)
    assert data.hex(" ").upper() in dialog.editor.toPlainText()
    assert datetime.fromtimestamp(timestamp).isoformat(timespec="milliseconds") in dialog.editor.toPlainText()
    dialog.reject()
    assert not panel._dialogs


def test_log_table_preview_slices_before_hex_conversion(qtbot):
    class GuardedPayload(bytes):
        def hex(self, *_args, **_kwargs):
            raise AssertionError("Table preview formatted the entire large payload")

    panel = CommunicationPanel()
    qtbot.addWidget(panel)
    data = GuardedPayload(bytes(range(256)) * 4096)
    panel.append(LogEvent(level="RX", data=data, description="large payload"))
    assert len(panel.table.item(0, 2).text()) == 514
    assert panel.table.item(0, 2).data(Qt.ItemDataRole.UserRole) is data


def test_collapsed_navigation_still_selects_lazily_loaded_pages(window_factory, qtbot):
    _, window = window_factory()
    window.show()
    window.navigation.setCurrentRow(5)
    qtbot.waitUntil(lambda: window.pages.count() == len(PAGE_DEFINITIONS))
    assert window.pages.currentIndex() == 5
    original_width = window.sidebar.width()
    labels = [window.navigation.item(index).text() for index in range(window.navigation.count())]
    window.collapse_button.click()
    assert window.sidebar.width() < original_width
    assert all(window.navigation.item(index).text() == "" for index in range(len(labels)))
    assert all(window.navigation.item(index).toolTip() for index in range(len(labels)))
    window.navigation.setCurrentRow(3)
    assert window.pages.currentIndex() == 3
    window.collapse_button.click()
    assert window.sidebar.width() == original_width
    assert [window.navigation.item(index).text() for index in range(len(labels))] == labels


def test_connection_and_hardware_dialog_apply_restore_and_cancel_are_session_local(window_factory):
    container, window = window_factory(demo=True)
    window.show_connection_settings()
    dialog = _latest_dialog(window, ConnectionDialog)
    dialog.address.setText("192.0.2.42")
    dialog.port.setText("4567")
    dialog.source.setText("abcd")
    dialog.apply_button.click()
    accepted = deepcopy(window._connection_settings)
    assert accepted["address"] == "192.0.2.42"
    assert accepted["port"] == 4567
    assert accepted["source"] == "0xABCD"
    window.show_connection_settings()
    dialog = _latest_dialog(window, ConnectionDialog)
    assert dialog.address.text() == accepted["address"]
    dialog.address.setText("192.0.2.99")
    dialog.cancel_button.click()
    assert window._connection_settings == accepted
    window.show_hardware_settings()
    hardware = _latest_dialog(window, HardwareDialog)
    hardware.can_model.setCurrentIndex(hardware.can_model.findData("TC1014"))
    hardware.apply_button.click()
    accepted_hardware = deepcopy(window._hardware_settings)
    assert accepted_hardware["can_model"] == "TC1014"
    window.show_hardware_settings()
    hardware = _latest_dialog(window, HardwareDialog)
    assert hardware.can_model.currentData() == "TC1014"
    hardware.can_model.setCurrentIndex(hardware.can_model.findData("TC1016"))
    hardware.cancel_button.click()
    assert window._hardware_settings == accepted_hardware
    assert not window._preview_connected
    assert not (container.paths.root / "config").exists()


def test_window_close_releases_timers_animation_all_child_dialogs_and_late_logs(window_factory, qtbot):
    container, window = window_factory(demo=True)
    window.show()
    window._show_toast("test feedback")
    window._fade_toast()
    assert window._toast_timer.isActive()
    assert window._toast_animation.state() == QAbstractAnimation.State.Running
    for open_dialog in (
        window.show_connection_settings, window.show_hardware_settings, window.show_byte_preview,
        window.show_capture, window.show_about, window.command_editor.import_commands,
        window.command_editor.export_commands, window.communication.export_logs,
    ):
        open_dialog()
    dialogs = window.findChildren(QDialog)
    assert len(dialogs) >= 8
    assert all(dialog.isVisible() for dialog in dialogs)
    destroyed = []
    for index, dialog in enumerate(dialogs):
        dialog.destroyed.connect(lambda _object=None, marker=index: destroyed.append(marker))
    retained_logs = tuple(window.communication.records)
    window.close()
    assert not window._page_timer.isActive()
    assert not window._toast_timer.isActive()
    assert window._toast_animation.state() == QAbstractAnimation.State.Stopped
    assert window.toast.isHidden()
    assert not window._dialogs
    assert not window.communication._dialogs
    container.event_bus.publish(LogEvent(level="ERROR", data=None, description="late event"))
    assert tuple(window.communication.records) == retained_logs
    qtbot.waitUntil(lambda: len(destroyed) == len(dialogs))
    container.shutdown()
    assert not container.file_logging.thread.is_alive()
