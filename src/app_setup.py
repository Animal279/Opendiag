"""Runtime initialization and smoke utility; no automation CLI is provided."""

import argparse
import json
import os
from pathlib import Path
import struct
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenDiag 开发预览")
    parser.add_argument("--smoke-test", action="store_true", help="启动窗口并校验延迟页面后退出")
    parser.add_argument("--ui-demo", action="store_true", help="启动本地 UI 演示，无 ECU / 硬件 IO")
    parser.add_argument("--app-root", type=Path, help="显式应用数据根目录")
    args = parser.parse_args(argv)
    if sys.version_info[:3] != (3, 12, 10) or struct.calcsize("P") != 8:
        print("OpenDiag 当前基线要求 Python 3.12.10 x64。", file=sys.stderr)
        return 2
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QObject, QTimer, Slot
    from PySide6.QtWidgets import QApplication
    from src.application.app_container import AppContainer
    from src.ports.events import LogEvent
    from src.ui.theme import apply_application_theme
    from src.version import __version__

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("OpenDiag")
    app.setApplicationVersion(__version__)
    apply_application_theme(app)

    class SmokeCheck(QObject):
        def __init__(self):
            super().__init__(window)
            self.passed = False
            self.timer = QTimer(self)
            self.timer.setInterval(0)
            self.timer.timeout.connect(self.check)
            self.deadline = QTimer(self)
            self.deadline.setSingleShot(True)
            self.deadline.timeout.connect(self.timeout)

        @Slot()
        def check(self):
            if window.pages.count() == window.navigation.count():
                self.passed = True
                self.timer.stop()
                self.deadline.stop()
                print(json.dumps({"version": __version__, "pages": window.pages.count(),
                                  "hardware_initialized": False, "smoke": "passed"}))
                window.close()

        @Slot()
        def timeout(self):
            self.timer.stop()
            print("工程骨架页面加载超时。", file=sys.stderr)
            window.close()

        def start(self):
            self.timer.start()
            self.deadline.start(5000)

    container = AppContainer(args.app_root)
    window = None
    smoke = None
    try:
        window = container.create_window(ui_demo=True) if args.ui_demo else container.create_window()
        window.show()
        container.event_bus.publish(LogEvent(
            level="INFO", data=None, description=f"界面预览启动 {__version__}；未创建硬件连接"
        ))
        if args.smoke_test:
            smoke = SmokeCheck()
            smoke.start()
        result = app.exec()
    finally:
        try:
            if window is not None:
                window.close()
        finally:
            container.shutdown()
    return 1 if smoke is not None and not smoke.passed else result
