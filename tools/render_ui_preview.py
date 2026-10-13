"""Reproduce local Qt screenshots without starting hardware or writing config."""

import argparse
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("local/evidence/ds-01"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject, QTimer, Slot
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication
    from src.application.app_container import AppContainer
    from src.ports.events import LogEvent
    from src.ui.config_dialogs import ConnectionDialog, HardwareDialog
    from src.ui.theme import apply_application_theme

    app = QApplication.instance() or QApplication([])
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("msyh.ttc", "msyhbd.ttc", "consola.ttf", "consolab.ttf"):
        if (fonts / name).is_file():
            QFontDatabase.addApplicationFont(str(fonts / name))
    apply_application_theme(app)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    class Renderer(QObject):
        def __init__(self, window):
            super().__init__(window)
            self.window = window
            self.succeeded = False
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.render)
            self.timer.start(0)
            self.deadline = QTimer(self)
            self.deadline.setSingleShot(True)
            self.deadline.timeout.connect(self.timeout)
            self.deadline.start(5000)

        def save(self, widget, name):
            app.processEvents()
            if not widget.grab().save(str(output / name)):
                raise RuntimeError(f"Unable to save {name}")
            print(name)

        @Slot()
        def render(self):
            if self.window.pages.count() != 6:
                return
            self.timer.stop()
            self.deadline.stop()
            normal = None
            try:
                window = self.window
                window.toggle_preview_connection()
                window.command_editor.send_checked()
                window._toast_timer.stop()
                window.toast.hide()
                self.save(window, "ui-demo-uds.png")
                other_pages = ((1, "automation"), (2, "flash"), (3, "dtc"), (4, "doip"), (5, "doip-automation"))
                for index, name in other_pages:
                    window.navigation.setCurrentRow(index)
                    self.save(window, f"ui-demo-{name}.png")
                window.navigation.setCurrentRow(0)
                container.event_bus.publish(LogEvent(
                    level="INFO", data=bytes(range(256)) * 2,
                    description="UI 布局验证：长数据只用于检查显示、截短和复制入口；未发送报文。",
                ))
                self.save(window, "ui-demo-long-data.png")
                window.toggle_navigation()
                self.save(window, "ui-demo-collapsed.png")
                window.toggle_navigation()
                window.resize(1080, 680)
                self.save(window, "ui-demo-minimum.png")
                if window.size().width() != 1080 or window.size().height() != 680:
                    raise RuntimeError("Minimum window grew beyond 1080x680")
                for index, name in other_pages:
                    window.navigation.setCurrentRow(index)
                    self.save(window, f"ui-demo-{name}-minimum.png")
                window.navigation.setCurrentRow(0)
                window.command_editor.addressing_selector.functional_button.click()
                window.command_editor.keep_alive_button.click()
                window.command_editor.keep_alive_button.setFocus()
                window.command_editor.command_input.setText("10 0")
                window.command_editor.add_current()
                window._toast_timer.stop()
                window.toast.hide()
                self.save(window, "ui-demo-controls-error-focus.png")
                for cls, name in ((ConnectionDialog, "connection"), (HardwareDialog, "hardware")):
                    dialog = cls(window)
                    dialog.open()
                    self.save(dialog, f"ui-demo-{name}.png")
                    dialog.resize(540, 400)
                    self.save(dialog, f"ui-demo-{name}-minimum.png")
                    if isinstance(dialog, ConnectionDialog):
                        dialog.address.setText("invalid")
                        dialog.apply_button.click()
                        self.save(dialog, "ui-demo-connection-error.png")
                    dialog.reject()
                window.close()
                normal = container.create_window()
                normal.show()
                self.save(normal, "ui-default-disabled.png")
                normal.close()
                self.succeeded = True
            except Exception as error:
                print(f"UI preview failed: {error}", file=sys.stderr)
            finally:
                if normal is not None:
                    normal.close()
                self.window.close()
                app.quit()

        @Slot()
        def timeout(self):
            self.timer.stop()
            print("UI preview timed out", file=sys.stderr)
            self.window.close()

    with TemporaryDirectory(prefix="opendiag-ui-render-") as data_root:
        container = AppContainer(data_root)
        window = None
        try:
            window = container.create_window(ui_demo=True)
            window.show()
            renderer = Renderer(window)
            app.exec()
            return 0 if renderer.succeeded else 1
        finally:
            if window is not None:
                window.close()
            container.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
