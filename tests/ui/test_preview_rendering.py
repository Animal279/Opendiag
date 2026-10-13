"""A failed final screenshot must exit and release both preview windows."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_final_preview_save_failure_closes_windows_and_logging_thread(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "previews"
    wrapper = textwrap.dedent('''
        from pathlib import Path
        import sys
        from PySide6.QtGui import QPixmap
        from src.application.app_container import AppContainer
        from tools import render_ui_preview

        windows = []
        create_window = AppContainer.create_window
        shutdown = AppContainer.shutdown
        save = QPixmap.save

        def capture_window(self, *args, **kwargs):
            window = create_window(self, *args, **kwargs)
            windows.append(window)
            return window

        def checked_shutdown(self):
            shutdown(self)
            assert len(windows) == 2
            assert all(not window.isVisible() and window._closing for window in windows)
            print("ALL_PREVIEW_WINDOWS_CLOSED", flush=True)
            assert not self.file_logging.thread.is_alive()
            print("PREVIEW_LOGGING_THREAD_STOPPED", flush=True)

        def fail_final_save(self, filename, *args):
            if Path(filename).name == "ui-default-disabled.png":
                return False
            return save(self, filename, *args)

        AppContainer.create_window = capture_window
        AppContainer.shutdown = checked_shutdown
        QPixmap.save = fail_final_save
        sys.argv = ["render_ui_preview.py", "--output", sys.argv[1]]
        raise SystemExit(render_ui_preview.main())
    ''')
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-c", wrapper, str(output)], cwd=root, env=environment,
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "UI preview failed:" in result.stderr
    assert "Unable to save ui-default-disabled.png" in result.stderr
    assert "ALL_PREVIEW_WINDOWS_CLOSED" in result.stdout
    assert "PREVIEW_LOGGING_THREAD_STOPPED" in result.stdout
    assert (output / "ui-demo-uds.png").is_file()
    assert (output / "ui-demo-hardware.png").is_file()
    assert not (output / "ui-default-disabled.png").exists()
