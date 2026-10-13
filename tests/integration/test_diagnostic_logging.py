from src.application.app_container import AppContainer
from src.ports.events import LogEvent
from src.ports.events import DataReceivedEvent, RoutingActivationResponseEvent
from src.ports.model_types import DoIPSettings
from dataclasses import replace
from tests.domain.test_connection_settings import sample_config
from tests.fixtures.fake_doip_server import FakeDoIPServer


def test_full_bytes_and_source_time_are_written_in_background(qapp, tmp_path):
    container = AppContainer(tmp_path)
    container.event_bus.publish(LogEvent("RX", bytes.fromhex("11100e805003003201f4"), "source", timestamp=123.25))
    container.shutdown()
    text = container.file_logging.log_file.read_text(encoding="utf-8")
    assert "11 10 0E 80 50 03 00 32 01 F4" in text
    assert "123.250000" in text


def test_log_disk_failure_is_visible_in_application(qtbot, tmp_path):
    (tmp_path / "logs").write_text("blocked")
    container = AppContainer(tmp_path)
    window = container.create_window()
    qtbot.addWidget(window)
    try:
        qtbot.waitUntil(lambda: "日志写入失败" in window.log_view.toPlainText())
    finally:
        window.close(); container.shutdown()


def test_incomplete_frame_keeps_all_bytes_in_log_without_uds_or_ra_success(qtbot, tmp_path):
    # Declares 300 payload bytes but closes with 271; the tail is beyond UI preview.
    partial = bytes.fromhex("02fd80010000012c11100e80") + bytes(range(256)) + b"tail-proof!"
    assert len(partial) == 279
    with FakeDoIPServer() as server:
        server.queue_response(partial, close_after=True)
        container = AppContainer(tmp_path)
        logs, uds, routing = [], [], []
        container.event_bus.subscribe(LogEvent, logs.append)
        container.event_bus.subscribe(DataReceivedEvent, uds.append)
        container.event_bus.subscribe(RoutingActivationResponseEvent, routing.append)
        settings = replace(DoIPSettings.from_config(sample_config()), target_ip="127.0.0.1", target_port=server.port)
        try:
            assert container.manual_diagnostic.connect(settings)
            qtbot.waitUntil(lambda: any("未完成 DoIP" in event.description for event in logs))
            qtbot.waitUntil(container.doip_adapter.is_quiescent)
            incomplete = [event for event in logs if event.data == partial]
            assert len(incomplete) == 1, "Incomplete bytes must be recoverable in raw logs"
            assert "未完成" in incomplete[0].description
            assert uds == [] and routing == []
        finally:
            container.shutdown()
        text = container.file_logging.log_file.read_text(encoding="utf-8")
        assert partial.hex(" ").upper() in text
