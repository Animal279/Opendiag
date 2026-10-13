from src.application.app_container import AppContainer
from src.ports.events import LogEvent
from src.ui.main_window import PAGE_DEFINITIONS


def test_lazy_pages_navigation_and_shutdown(qtbot, tmp_path):
    container = AppContainer(tmp_path)
    window = container.create_window()
    qtbot.addWidget(window)
    try:
        assert window.pages.count() == 1
        window.show()
        qtbot.waitUntil(lambda: window.pages.count() == len(PAGE_DEFINITIONS))
        window.navigation.setCurrentRow(5)
        assert window.pages.currentIndex() == 5
        assert not window.connect_button.isEnabled()
        assert window.project_label.text() == "项目：未加载"
        assert not (tmp_path / "config").exists()
        window.close()
        assert not window._page_timer.isActive()
    finally:
        window.close()
        container.shutdown()
    assert not container.file_logging.thread.is_alive()


def test_application_log_filter_and_unsubscribe(qtbot, tmp_path):
    container = AppContainer(tmp_path)
    window = container.create_window()
    qtbot.addWidget(window)
    try:
        for level in ("DEBUG", "INFO", "TX", "RX", "WARN", "ERROR"):
            container.event_bus.publish(LogEvent(level=level, data=None, description=f"test {level}"))
        assert window.log_view.toPlainText().splitlines() == ["[WARN] test WARN", "[ERROR] test ERROR"]
        window.close()
        container.event_bus.publish(LogEvent(level="ERROR", data=None, description="late"))
        assert "late" not in window.log_view.toPlainText()
    finally:
        window.close()
        container.shutdown()

