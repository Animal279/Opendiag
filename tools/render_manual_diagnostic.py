"""Explicit loopback-only visual QA for the real UDS UI, never a company ECU."""

import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "local/evidence/manual-2026-10-11")
    parser.add_argument("--response-inspection", action="store_true", help="额外生成 UDS 响应和本地解析预览")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    from PySide6.QtCore import QObject, QTimer, Slot
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication
    from src.application.app_container import AppContainer
    from src.ports.model_types import SessionState
    from src.ui.config_dialogs import DiagnosticConnectionDialog
    from src.ui.main_window import BytePreviewDialog
    from src.ui.theme import apply_application_theme
    from tests.fixtures.fake_doip_server import FakeDoIPServer

    app = QApplication.instance() or QApplication([])
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("msyh.ttc", "msyhbd.ttc", "consola.ttf", "consolab.ttf"):
        if (fonts / name).is_file():
            QFontDatabase.addApplicationFont(str(fonts / name))
    apply_application_theme(app)
    with TemporaryDirectory(prefix="opendiag-manual-preview-") as directory, FakeDoIPServer() as server:
        config = json.loads((root / "examples/projects/LoopbackDemo/config.json").read_text(encoding="utf-8"))
        config["doip"].update(target_ip="127.0.0.1", target_port=server.port)
        path = Path(directory) / "config/LoopbackDemo/config.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(config), encoding="utf-8")
        server.queue_response(bytes.fromhex("02fd0006000000090e8011101000000000"))
        server.queue_response(bytes.fromhex("02fd80010000000a11100e805003003201f4"))
        container = AppContainer(directory)
        window = container.create_window()

        class Renderer(QObject):
            def __init__(self):
                super().__init__(window)
                self.phase = 0
                self.passed = False
                self.deadline = time.monotonic() + 8
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.tick)
                self.timer.start(20)

            def save(self, widget, name):
                app.processEvents()
                if not widget.grab().save(str(output / name)):
                    raise RuntimeError(f"Unable to save {name}")
                print(name)

            @Slot()
            def tick(self):
                try:
                    if time.monotonic() > self.deadline:
                        raise RuntimeError("Manual rendering timeout")
                    state = container.manual_diagnostic.snapshot.state
                    if self.phase == 0 and container.projects.current and not container.projects.busy:
                        window.show_connection_settings()
                        self.dialog = window.findChildren(DiagnosticConnectionDialog)[-1]
                        self.save(self.dialog, "connection-config.png")
                        self.dialog.hide()
                        window.connect_button.click()
                        self.phase = 1
                    elif self.phase == 1 and state is SessionState.READY:
                        window.command_editor.command_input.setText("10 03")
                        window.command_editor.send_current()
                        self.phase = 2
                    elif self.phase == 2 and any(e.level == "RX" and e.data and e.data.endswith(bytes.fromhex("5003003201f4")) for e in window.communication.records):
                        window._toast_timer.stop()
                        window.toast.hide()
                        self.save(window, "uds-ready.png")
                        window.resize(1080, 680)
                        self.save(window, "uds-ready-minimum.png")
                        if window.size().width() != 1080 or window.size().height() != 680:
                            raise RuntimeError("Minimum window exceeds 1080x680")
                        if args.response_inspection:
                            panel = window.communication.response_panel
                            if "5000 ms" not in panel.timing_label.text():
                                raise RuntimeError("UDS server timing not displayed")
                            window.communication.tabs.setCurrentWidget(panel)
                            window.resize(1440, 860)
                            self.save(window, "uds-response.png")
                            window.resize(1080, 680)
                            self.save(window, "uds-response-minimum.png")
                            if window.width() != 1080 or window.height() != 680:
                                raise RuntimeError("Response panel exceeds minimum window")
                            window.show_byte_preview()
                            preview = window.findChildren(BytePreviewDialog)[-1]
                            preview.input_kind.setCurrentIndex(1)
                            preview.editor.setPlainText("02 FD 80 01 00 00 00 0A 11 10 0E 80 50 03 00 32 01 F4")
                            self.save(preview, "uds-parser.png")
                            preview.editor.setPlainText("02 FD 80 01 00 00 00 0A 11 10")
                            self.save(preview, "uds-parser-invalid.png")
                            preview.reject()
                            window.communication.tabs.setCurrentIndex(0)
                        self.dialog.show()
                        self.dialog.accept()
                        self.save(self.dialog, "connection-locked.png")
                        self.dialog.reject()
                        server.stop()
                        self.phase = 3
                    elif self.phase == 3 and state is SessionState.FAILED:
                        self.save(window, "uds-failed-minimum.png")
                        window.resize(1440, 860)
                        self.save(window, "uds-failed.png")
                        self.passed = True
                        self.timer.stop()
                        window.close()
                        app.quit()
                except Exception as exc:
                    print(f"Render failed: {exc}", file=sys.stderr)
                    self.timer.stop()
                    window.close()
                    app.quit()

        renderer = Renderer()
        try:
            window.show()
            window.diagnostic_controller.load_project("LoopbackDemo")
            app.exec()
        finally:
            window.close()
            container.shutdown()
        return 0 if renderer.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
