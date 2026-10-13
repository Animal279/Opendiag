"""Local configuration previews must reject invalid input without device IO."""

from copy import deepcopy

import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QDialog, QPushButton

from src.ui.config_dialogs import ConnectionDialog, HardwareDialog


@pytest.fixture
def dialogs(qapp):
    created = []

    def create(cls, state=None):
        dialog = cls(state=state)
        created.append(dialog)
        dialog.open()
        qapp.processEvents()
        return dialog

    yield create
    for dialog in created:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


def test_connection_open_is_nonblocking_and_accepts_explicit_preview(dialogs):
    dialog = dialogs(ConnectionDialog)
    accepted = QSignalSpy(dialog.accepted)
    assert dialog.isVisible()
    assert "未加载真实项目" in dialog.project.text()

    dialog.accept()

    assert accepted.count() == 1
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values["transport"] == "doip"
    assert dialog.values["project"] == "UI 演示"
    assert dialog.values["address"] == "127.0.0.1"
    assert dialog.values["port"] == 13400
    assert dialog.values["source"] == "0x0E80"
    assert dialog.values["target"] == "0x0001"


@pytest.mark.parametrize("address", ["not-an-ip", "999.0.0.1", ""])
def test_invalid_ip_remains_editable_and_does_not_accept(dialogs, address):
    dialog = dialogs(ConnectionDialog)
    accepted = QSignalSpy(dialog.accepted)
    dialog.address.setText(address)

    dialog.accept()

    assert accepted.count() == 0
    assert dialog.isVisible()
    assert dialog.address.text() == address
    assert "有效的 IPv4 或 IPv6" in dialog.error_label.text()
    assert dialog.values == {}


@pytest.mark.parametrize("port", ["0", "65536", "abc", "１３４００", "9" * 5000])
def test_invalid_port_is_not_clamped_or_replaced(dialogs, port):
    dialog = dialogs(ConnectionDialog)
    accepted = QSignalSpy(dialog.accepted)
    dialog.port.setText(port)

    dialog.accept()

    assert accepted.count() == 0
    assert dialog.isVisible()
    assert dialog.port.text() == port
    assert "1–65535" in dialog.error_label.text()


@pytest.mark.parametrize("field_name,text", [("source", "ZZ"), ("target", "0x10000")])
def test_invalid_logic_address_does_not_discard_input(dialogs, field_name, text):
    dialog = dialogs(ConnectionDialog)
    accepted = QSignalSpy(dialog.accepted)
    field = getattr(dialog, field_name)
    field.setText(text)

    dialog.accept()

    assert accepted.count() == 0
    assert field.text() == text
    assert dialog.error_label.isVisible()
    assert dialog.isVisible()


def test_transport_switch_preserves_fields_and_docan_values_contract(dialogs):
    dialog = dialogs(ConnectionDialog)
    dialog.address.setText("192.0.2.8")
    dialog.source.setText("0e81")
    dialog.transport.setCurrentIndex(dialog.transport.findData("docan"))
    assert dialog.protocol_pages.currentIndex() == 1
    assert dialog.req_id.isVisible()
    assert not dialog.address.isVisible()
    dialog.req_id.setText("0x721")

    dialog.transport.setCurrentIndex(dialog.transport.findData("doip"))
    assert dialog.protocol_pages.currentIndex() == 0
    assert dialog.address.text() == "192.0.2.8"
    assert dialog.source.text() == "0e81"
    dialog.transport.setCurrentIndex(dialog.transport.findData("docan"))
    assert dialog.req_id.text() == "0x721"
    dialog.accept()

    values = dialog.values
    assert values["transport"] == "docan"
    assert values["docan"]["req_id"] == "0x721"
    assert values["docan"]["is_extended"] is False
    assert values["docan"]["is_canfd"] is False
    assert isinstance(values["port"], int)
    assert all(key in values for key in ("project", "address", "source", "target"))


def test_invalid_hidden_port_does_not_silently_return_demo_port(dialogs):
    dialog = dialogs(ConnectionDialog)
    accepted = QSignalSpy(dialog.accepted)
    dialog.port.setText("bad-port")
    dialog.transport.setCurrentIndex(dialog.transport.findData("docan"))

    dialog.accept()

    assert accepted.count() == 0
    assert dialog.port.text() == "bad-port"
    assert "切换到 DoIP" in dialog.error_label.text()


def test_docan_id_validates_the_selected_frame_width(dialogs):
    dialog = dialogs(ConnectionDialog, {"transport": "docan"})
    accepted = QSignalSpy(dialog.accepted)
    dialog.req_id.setText("0x800")

    dialog.accept()

    assert accepted.count() == 0
    assert "0x7FF" in dialog.error_label.text()
    assert dialog.req_id.text() == "0x800"
    dialog.extended.setChecked(True)
    dialog.accept()
    assert accepted.count() == 1
    assert dialog.values["docan"]["req_id"] == "0x00000800"


def test_cancel_and_values_snapshot_leave_original_state_unchanged(dialogs):
    state = {"address": "192.0.2.10", "port": 13400, "docan": {"req_id": "0x721"}}
    original = deepcopy(state)
    dialog = dialogs(ConnectionDialog, state)
    rejected = QSignalSpy(dialog.rejected)
    dialog.address.setText("192.0.2.11")
    dialog.cancel_button.click()

    assert rejected.count() == 1
    assert state == original
    assert dialog.values == {}

    accepted_dialog = dialogs(ConnectionDialog, state)
    accepted_dialog.accept()
    snapshot = accepted_dialog.values
    snapshot["docan"]["req_id"] = "changed"
    assert accepted_dialog.values["docan"]["req_id"] == "0x721"
    assert state == original


def test_hardware_stays_unselected_and_device_operations_unavailable(dialogs):
    dialog = dialogs(HardwareDialog)
    for name in ("hardwareInitCan", "hardwareTestPower", "hardwareResources"):
        assert not dialog.findChild(QPushButton, name).isEnabled()
    dialog.accept()

    assert dialog.values["can_model"] is None
    assert dialog.values["can_channel"] is None
    assert dialog.values["power_model"] is None
    assert dialog.values["serial_port"] == ""
    assert dialog.values["baudrate"] is None


def test_hardware_invalid_serial_remains_editable(dialogs):
    dialog = dialogs(HardwareDialog)
    accepted = QSignalSpy(dialog.accepted)
    dialog.serial_port.setText("COM0")

    dialog.accept()

    assert accepted.count() == 0
    assert dialog.serial_port.text() == "COM0"
    assert "COM 加正整数" in dialog.error_label.text()
    assert dialog.isVisible()
    dialog.serial_port.setText("com12")
    dialog.accept()
    assert accepted.count() == 1
    assert dialog.values["serial_port"] == "COM12"


@pytest.mark.parametrize("state", [{"can_model": "fake-device"}, {"power_model": "fake-power"}])
def test_unknown_hardware_model_never_silently_falls_back(dialogs, state):
    original = deepcopy(state)
    dialog = dialogs(HardwareDialog, state)
    accepted = QSignalSpy(dialog.accepted)

    dialog.accept()

    assert accepted.count() == 0
    assert "不在已确认型号列表" in dialog.error_label.text()
    assert dialog.values == {}
    assert state == original
    assert dialog.isVisible()
