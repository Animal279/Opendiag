from dataclasses import replace
import socket
import threading
import time

from PySide6.QtCore import QCoreApplication, QEvent, Qt

from src.adapters.doip_adapter import DoIPAdapter
from src.adapters.qt_event_bus import QtDomainEventBus
from src.core.doip_protocol import DoIPProtocol
from src.domain.connection_models import DoIPSettings
from src.domain.events import (ConnectionEvent, DataReceivedEvent, DataSentEvent,
                               DoIPMessageReceivedEvent, RoutingActivationResponseEvent,
                               DiagnosticAckEvent, ErrorEvent, LogEvent)
from tests.domain.test_connection_settings import sample_config
from tests.fixtures.fake_doip_server import FakeDoIPServer

RA = bytes.fromhex("02fd0006000000090e8011101000000000")
UDS = bytes.fromhex("02fd80010000000a11100e805003003201f4")


def make_transport(port):
    settings = replace(DoIPSettings.from_config(sample_config()), target_ip="127.0.0.1", target_port=port)
    bus = QtDomainEventBus()
    protocol = DoIPProtocol()
    adapter = DoIPAdapter(protocol, bus)
    adapter.configure(settings)
    return bus, protocol, adapter


def test_real_wire_uds_raw_and_ack_are_distinct_and_main_thread(qtbot):
    with FakeDoIPServer() as server:
        server.queue_response(RA)
        # Full UDS, ACK, wrong source and wrong target remain independently observable.
        server.queue_response(UDS + bytes.fromhex("02fd80020000000511100e8000")
                              + bytes.fromhex("02fd80010000000622220e805003")
                              + bytes.fromhex("02fd800100000006111099995003"))
        bus, protocol, adapter = make_transport(server.port)
        received, raws, acknowledgments, routing, sent, logs, owners = [], [], [], [], [], [], []
        for cls, target in ((DataReceivedEvent, received), (DoIPMessageReceivedEvent, raws),
                            (DiagnosticAckEvent, acknowledgments), (RoutingActivationResponseEvent, routing),
                            (DataSentEvent, sent), (LogEvent, logs)):
            bus.subscribe(cls, target.append)
        def on_rx(event):
            owners.append(threading.get_ident())
        bus.subscribe(DataReceivedEvent, on_rx)
        assert adapter.connect("127.0.0.1", server.port)
        qtbot.waitUntil(adapter.is_connected)
        assert adapter.send_routing_activation()
        qtbot.waitUntil(lambda: len(routing) == 1)
        assert routing[0].is_success
        assert adapter.send_diagnostic_message(b"\x10\x03")
        qtbot.waitUntil(lambda: len(raws) == 5)
        assert [event.data for event in received] == [bytes.fromhex("5003003201f4")]
        assert owners == [threading.get_ident()]
        assert len(acknowledgments) == 1 and acknowledgments[0].is_positive
        assert [event.data.hex() for event in sent] == ["02fd00050000000b0e800000000000ffffffff", "02fd8001000000060e8011101003"]
        assert len([event for event in logs if event.level == "RX"]) == 5
        adapter.disconnect()
        qtbot.waitUntil(adapter.is_quiescent)
        assert not adapter.send_diagnostic_message(b"\x10\x03")
        adapter.shutdown()
        bus.close()


class ControlledSocket:
    def __init__(self, *, slow_connect=False, fail_send=False):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.closed = threading.Event()
        self.slow_connect = slow_connect
        self.fail_send = fail_send
        self.send_calls = []
        self.connect_owner = None
        self._fd = 1

    def setsockopt(self, *args): pass
    def settimeout(self, value): pass
    def fileno(self): return self._fd
    def connect(self, address):
        self.connect_owner = threading.get_ident()
        self.entered.set()
        if self.slow_connect:
            assert self.release.wait(2)
    def recv(self, size):
        self.closed.wait(0.05)
        if self.closed.is_set(): return b""
        raise socket.timeout()
    def sendall(self, data):
        self.send_calls.append((data, time.time(), threading.get_ident()))
        if self.fail_send: raise OSError("write failed")
    def shutdown(self, how): self.closed.set()
    def close(self):
        self.closed.set()
        self._fd = -1


def test_cancel_slow_connect_and_stale_callbacks_cannot_revive_session(qtbot, monkeypatch):
    controlled = ControlledSocket(slow_connect=True)
    monkeypatch.setattr("src.core.doip_protocol.socket.socket", lambda *args: controlled)
    bus, protocol, adapter = make_transport(13400)
    connections = []
    bus.subscribe(ConnectionEvent, connections.append)
    assert adapter.connect("127.0.0.1", 13400)
    assert controlled.entered.wait(1)
    assert controlled.connect_owner != threading.get_ident()
    # Qt continues running while connect is blocked.
    qtbot.waitUntil(lambda: True)
    adapter.disconnect()
    controlled.release.set()
    qtbot.waitUntil(adapter.is_quiescent)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
    assert not adapter.is_connected()
    assert not any(e.connected for e in connections)
    assert controlled.fileno() == -1
    previous = adapter.generation
    adapter.connect("127.0.0.1", 13400)
    assert adapter.generation > previous
    protocol.frame_received.emit(previous, RA, 10.0)
    adapter.disconnect()
    qtbot.waitUntil(adapter.is_quiescent)
    adapter.shutdown()
    bus.close()


def test_data_sent_is_before_sendall_and_write_error_is_separate(qtbot, monkeypatch):
    controlled = ControlledSocket(fail_send=True)
    monkeypatch.setattr("src.core.doip_protocol.socket.socket", lambda *args: controlled)
    bus, protocol, adapter = make_transport(13400)
    errors, sent = [], []
    bus.subscribe(ErrorEvent, errors.append)
    bus.subscribe(DataSentEvent, sent.append)
    wire_times = []
    protocol.sending.connect(lambda g, data, stamp: wire_times.append(stamp), Qt.ConnectionType.DirectConnection)
    adapter.connect("127.0.0.1", 13400)
    qtbot.waitUntil(adapter.is_connected)
    adapter.send_routing_activation()
    qtbot.waitUntil(lambda: bool(errors))
    qtbot.waitUntil(adapter.is_quiescent)
    assert len(sent) == 1
    assert "write failed" in errors[0].message
    assert wire_times[0] <= controlled.send_calls[0][1]
    assert controlled.send_calls[0][2] != threading.get_ident()
    assert controlled.fileno() == -1
    adapter.shutdown()
    bus.close()


def test_half_frame_close_and_ra_followed_by_immediate_close(qtbot):
    for response in (RA[:-1], RA):
        with FakeDoIPServer() as server:
            server.queue_response(response)
            bus, protocol, adapter = make_transport(server.port)
            routing, errors = [], []
            bus.subscribe(RoutingActivationResponseEvent, routing.append)
            bus.subscribe(ErrorEvent, errors.append)
            adapter.connect("127.0.0.1", server.port)
            qtbot.waitUntil(adapter.is_connected)
            adapter.send_routing_activation()
            assert server.wait_for_received(1)
            server.stop()
            qtbot.waitUntil(adapter.is_quiescent)
            assert not adapter.is_connected()
            if response != RA:
                qtbot.waitUntil(lambda: bool(errors))
                assert routing == []
            adapter.shutdown()
            bus.close()


def test_alive_check_is_answered_and_connection_refusal_visible(qtbot):
    with FakeDoIPServer() as server:
        server.queue_response(bytes.fromhex("02fd000700000000"))
        bus, protocol, adapter = make_transport(server.port)
        adapter.connect("127.0.0.1", server.port)
        qtbot.waitUntil(adapter.is_connected)
        adapter.send_routing_activation()
        qtbot.waitUntil(lambda: len(server.received) == 2)
        assert server.received[1].hex() == "02fd0008000000020e80"
        adapter.shutdown()
        bus.close()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    bus, protocol, adapter = make_transport(port)
    errors = []
    bus.subscribe(ErrorEvent, errors.append)
    adapter.connect("127.0.0.1", port)
    qtbot.waitUntil(lambda: bool(errors))
    qtbot.waitUntil(adapter.is_quiescent)
    adapter.shutdown()
    bus.close()


def test_peer_fragmentation_and_success_then_close_same_delivery(qtbot):
    from src.application.manual_diagnostic_service import ManualDiagnosticService
    from src.ports.events import SessionStateChangedEvent
    from src.ports.model_types import SessionState
    with FakeDoIPServer() as server:
        gate = threading.Event()
        server.queue_response(RA, chunks=(1, 4, 3, 2), close_after=True, reply_gate=gate)
        bus, protocol, adapter = make_transport(server.port)
        closed = threading.Event()
        def observe_close(generation, connected, stamp):
            if not connected:
                closed.set()
        protocol.connection_changed.connect(observe_close, Qt.ConnectionType.DirectConnection)
        service = ManualDiagnosticService(adapter, adapter, bus)
        history = []
        bus.subscribe(SessionStateChangedEvent, lambda event: history.append(event.snapshot.state))
        service.connect(adapter._settings)
        qtbot.waitUntil(lambda: service.snapshot.state is SessionState.ACTIVATING)
        gate.set()
        assert server.wait_for_stopped(2)
        # Wait for the receiver's EOF before pumping queued RA callbacks.
        # Server shutdown alone does not prove that the client has read EOF.
        assert closed.wait(2)
        qtbot.waitUntil(adapter.is_quiescent)
        # Deliver RA and EOF after the peer has physically closed.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
        service.poll()
        assert SessionState.READY not in history
        assert not service.send(b"\x10\x03")
        service.close(); service.shutdown(); adapter.shutdown(); bus.close()


def test_slow_send_does_not_block_qt_and_release_waits_for_sender(qtbot, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    controlled = ControlledSocket()
    original = controlled.sendall
    def slow(data):
        entered.set()
        assert release.wait(2)
        original(data)
    controlled.sendall = slow
    monkeypatch.setattr("src.core.doip_protocol.socket.socket", lambda *args: controlled)
    bus, protocol, adapter = make_transport(13400)
    try:
        adapter.connect("127.0.0.1", 13400)
        qtbot.waitUntil(adapter.is_connected)
        assert adapter.send_routing_activation()
        assert entered.wait(1)
        from PySide6.QtCore import QObject, QTimer, Slot
        class Tick(QObject):
            def __init__(self): super().__init__(); self.observed = False
            @Slot()
            def observe(self): self.observed = True
        tick = Tick()
        QTimer.singleShot(0, tick.observe)
        qtbot.waitUntil(lambda: tick.observed)
        adapter.disconnect()
        assert not adapter.is_quiescent()
        release.set()
        qtbot.waitUntil(adapter.is_quiescent)
    finally:
        release.set(); adapter.shutdown(); bus.close()


def test_shutdown_cannot_start_receiver_after_join_snapshot(qtbot, monkeypatch):
    controlled = ControlledSocket()
    monkeypatch.setattr("src.core.doip_protocol.socket.socket", lambda *args: controlled)
    protocol = DoIPProtocol()
    before_registration, release_registration = threading.Event(), threading.Event()
    receive_entered, release_receive = threading.Event(), threading.Event()
    original_spawn = protocol._spawn
    original_receive = protocol._receive_worker

    def paused_spawn(session, name, action):
        if name == "doip-receive":
            before_registration.set()
            assert release_registration.wait(2)
        return original_spawn(session, name, action)

    def controlled_receive(session):
        receive_entered.set()
        assert release_receive.wait(2)
        original_receive(session)

    monkeypatch.setattr(protocol, "_spawn", paused_spawn)
    monkeypatch.setattr(protocol, "_receive_worker", controlled_receive)
    try:
        protocol.connect_to(DoIPSettings.from_config(sample_config()))
        assert before_registration.wait(1)
        connector = next(t for t in protocol._session.threads if t.name == "doip-connect")
        original_join = connector.join

        def join_after_snapshot(timeout=None):
            # The initial worker list has already been captured at this point.
            release_registration.set()
            original_join(timeout)

        monkeypatch.setattr(connector, "join", join_after_snapshot)
        protocol.shutdown()
        assert protocol.is_quiescent()
        assert controlled.fileno() == -1
        assert not receive_entered.is_set()
    finally:
        release_registration.set()
        release_receive.set()
        protocol.shutdown()
