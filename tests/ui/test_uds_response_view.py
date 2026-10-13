from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
import subprocess
import sys
from pathlib import Path

from src.ports.events import DataReceivedEvent
from src.ports.model_types import SessionState
from src.ui.main_window import BytePreviewDialog
from tests.integration.test_manual_diagnostic_workflow import RA, UDS, load_project, make_window
from tests.fixtures.fake_doip_server import FakeDoIPServer


def test_local_parser_handles_uds_and_explicit_doip_input_without_connection(qtbot):
    dialog = BytePreviewDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.editor.setPlainText("50 03 00 32 01 F4")
    assert "5000" in dialog.result_label.text()
    dialog.input_kind.setCurrentIndex(1)
    dialog.editor.setPlainText("02 FD 80 01 00 00 00 0A 11 10 0E 80 50 03 00 32 01 F4")
    assert "1110" in dialog.result_label.text() and "5000" in dialog.result_label.text()
    dialog.editor.setPlainText("02 FD 80 01 00 00 00 0A 11 10")
    assert dialog.inspection.error


def test_live_response_timing_survives_bad_frame_then_clears_on_disconnect(qtbot, tmp_path):
    with FakeDoIPServer() as server:
        server.queue_response(RA)
        server.queue_response(UDS)
        container, window = make_window(qtbot, tmp_path, server.port)
        try:
            load_project(qtbot, container, window)
            window.connect_button.click()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.READY)
            window.command_editor.command_input.setText("10 03")
            window.command_editor.send_current()
            qtbot.waitUntil(lambda: any(e.data == UDS for e in window.communication.records))
            panel = window.communication.response_panel
            assert "50 ms" in panel.timing_label.text() and "5000 ms" in panel.timing_label.text()
            assert panel.raw == bytes.fromhex("50 03 00 32 01 F4")
            container.event_bus.publish(DataReceivedEvent(b"\x50\x03"))
            assert panel.inspection.error
            assert "5000 ms" in panel.timing_label.text()
            panel.copy_button.click()
            assert QApplication.clipboard().text() == "50 03"
            container.event_bus.publish(DataReceivedEvent(bytes.fromhex("50 00 00 01 00 01")))
            assert panel.inspection.error
            assert "5000 ms" in panel.timing_label.text()
            window.connect_button.click()
            qtbot.waitUntil(lambda: container.manual_diagnostic.snapshot.state is SessionState.DISCONNECTED)
            assert panel.raw is None and not panel.copy_button.isEnabled()
            assert "5000" not in panel.timing_label.text()
            window.close()
            container.event_bus.publish(DataReceivedEvent(bytes.fromhex("50 03 00 32 01 F4")))
            assert panel.raw is None
        finally:
            window.close()
            container.shutdown()


def test_response_visual_renderer_produces_live_and_parser_evidence(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable,
                             str(root / "tools/render_manual_diagnostic.py"),
                             "--output", str(tmp_path), "--response-inspection"],
                            cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    for name in ("uds-response.png", "uds-response-minimum.png", "uds-parser.png", "uds-parser-invalid.png"):
        assert (tmp_path / name).is_file()


def test_minimum_window_response_view_has_complete_text_lines(qtbot, tmp_path):
    container, window = make_window(qtbot, tmp_path, 13400)
    try:
        window.resize(1080, 680)
        qtbot.waitUntil(lambda: window.pages.count() == 6)
        panel = window.communication.response_panel
        window.communication.tabs.setCurrentWidget(panel)
        panel.show_response(bytes.fromhex("50 03 00 32 01 F4"), 1.0)
        qtbot.waitExposed(window)
        required = 2 * panel.details.fontMetrics().lineSpacing() + int(2 * panel.details.document().documentMargin())
        qtbot.waitUntil(lambda: panel.details.viewport().height() >= required
                       and not panel.details.geometry().intersects(panel.copy_button.geometry()), timeout=1000)
        assert panel.details.viewport().height() >= required
        assert not panel.details.geometry().intersects(panel.copy_button.geometry())
        assert not panel.details.geometry().intersects(panel.source_label.geometry())
        for control in (panel.details, panel.copy_button, panel.source_label, panel.timing_label):
            bounds = QRect(panel.mapTo(panel.parentWidget(), control.pos()), control.size())
            assert panel.parentWidget().rect().contains(bounds)
        assert window.size().width() == 1080 and window.size().height() == 680
    finally:
        window.close()
        container.shutdown()
