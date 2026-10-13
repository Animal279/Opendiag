import json
from pathlib import Path

from src.application.app_container import AppContainer
from src.ports.model_types import SessionState
from src.ui.project_controls import ProjectControls
from tests.core.test_config_manager import write_project
from tests.fixtures.fake_doip_server import FakeDoIPServer

RA = bytes.fromhex("02fd0006000000090e8011101000000000")
UDS = bytes.fromhex("02fd80010000000a11100e805003003201f4")


def make_window(qtbot, tmp_path, port):
    container = AppContainer(tmp_path)
    original = Path(__file__).resolve().parents[2] / "examples/projects/LoopbackDemo/config.json"
    config = json.loads(original.read_text(encoding="utf-8"))
    config["doip"].update(target_ip="127.0.0.1", target_port=port, routing_timeout_ms=100)
    write_project(container.paths, "LoopbackDemo", config)
    window = container.create_window()
    qtbot.addWidget(window)
    window.show()
    return container, window


def load_project(qtbot, container, window):
    window.project_button.click()
    chooser = window.findChildren(ProjectControls)[-1]
    qtbot.waitUntil(lambda: chooser.project_combo.count() == 1)
    chooser.load_button.click()
    qtbot.waitUntil(lambda: container.projects.current is not None)
    qtbot.waitUntil(window.connect_button.isEnabled)


def test_complete_ui_project_activation_and_uds_wire_workflow(qtbot, tmp_path):
    with FakeDoIPServer() as server:
        server.queue_response(RA)
        server.queue_response(UDS)
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            assert not window.connect_button.isEnabled()
            load_project(qtbot, container, window)
            assert "LoopbackDemo" in window.project_label.text()
            window.connect_button.click()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.READY)
            assert "已激活" in window.connection_label.text()
            assert not window.settings_button.isEnabled()
            assert not window.project_button.isEnabled()
            window.command_editor.command_input.setText("10 03")
            window.command_editor.send_button.click()
            qtbot.waitUntil(lambda: any(e.data == UDS for e in window.communication.records))
            assert server.received == (
                bytes.fromhex("02fd00050000000b0e800000000000ffffffff"),
                bytes.fromhex("02fd8001000000060e8011101003"))
            assert [e.data for e in window.communication.records if e.level == "RX"] == [RA, UDS]
            qtbot.waitUntil(lambda: window.pages.count() == 6)
            doip = window.pages.widget(4)
            assert all(not b.isEnabled() for b in doip.findChildren(__import__('PySide6.QtWidgets', fromlist=['QPushButton']).QPushButton)
                       if b.text() in ("连接 Socket", "关闭 Socket", "发送"))
            window.connect_button.click()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.DISCONNECTED)
            assert window.settings_button.isEnabled()
            assert not window.command_editor.send_button.isEnabled()
        finally:
            window.close()
            container.shutdown()
        text = container.file_logging.log_file.read_text(encoding="utf-8")
        assert "50 03 00 32 01 F4" in text
        assert text.count("02 FD 80 01 00 00 00 0A") == 1
        assert not window.diagnostic_controller.timer.isActive()
        assert container.doip_adapter.is_quiescent()
