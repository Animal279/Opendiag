from dataclasses import replace
import threading

import pytest

from src.application.manual_diagnostic_service import ManualDiagnosticService
from src.domain.connection_models import DoIPSettings, SessionState
from src.domain.events import ConnectionEvent, RoutingActivationResponseEvent, ErrorEvent
from tests.domain.test_connection_settings import sample_config


class Bus:
    def __init__(self): self.subscribers = {}; self.events = []
    def subscribe(self, cls, handler): self.subscribers.setdefault(cls, []).append(handler)
    def unsubscribe(self, cls, handler): self.subscribers[cls].remove(handler)
    def publish(self, event):
        self.events.append(event)
        for handler in tuple(self.subscribers.get(type(event), ())): handler(event)


class Transport:
    def __init__(self):
        self.generation = 0; self.connected = False; self.released = True
        self.ra_count = 0; self.sends = []; self.sent = threading.Event()
        self.closed = 0
    def configure(self, settings): self.settings = settings
    def connect(self, ip, port):
        self.generation += 1; self.released = False; return True
    def is_connected(self): return self.connected
    def is_quiescent(self): return self.released
    def send_routing_activation(self): self.ra_count += 1; return self.connected
    def disconnect(self): self.connected = False; self.closed += 1
    def poll(self): pass
    def send_diagnostic_message(self, data, addressing="physical", *, generation=None):
        if generation != self.generation or not self.connected: return False
        self.sends.append((data, addressing, generation))
        self.sent.set()
        return True


def setup():
    bus, transport = Bus(), Transport()
    now = [0.0]
    service = ManualDiagnosticService(transport, transport, bus, clock=lambda: now[0])
    settings = DoIPSettings.from_config(sample_config())
    return bus, transport, service, settings, now


def activate(bus, transport, service, settings):
    assert service.connect(settings)
    transport.connected = True
    bus.publish(ConnectionEvent(True))
    bus.publish(RoutingActivationResponseEvent(0x0E80, 0x11, 0x10, True,
        bytes.fromhex("02fd0006000000090e8011101000000000")))


def cleanup(transport, service):
    service.close()
    transport.released = True
    service.shutdown()


def test_tcp_is_not_activation_and_only_ready_allows_manual_send():
    bus, transport, service, settings, now = setup()
    assert service.connect(settings)
    assert service.snapshot.state is SessionState.CONNECTING
    assert not service.send(b"\x10\x03")
    transport.connected = True
    bus.publish(ConnectionEvent(True))
    bus.publish(ConnectionEvent(True))
    assert transport.ra_count == 1
    assert service.snapshot.state is SessionState.ACTIVATING
    assert not service.send(b"\x10\x03")
    bus.publish(RoutingActivationResponseEvent(0x0E80, 0x11, 0x10, True,
        bytes.fromhex("02fd0006000000090e8011101000000000")))
    assert service.snapshot.state is SessionState.READY
    assert service.send(b"\x10\x03")
    assert service.send(b"\x3e\x80", "functional")
    assert transport.sends == [(b"\x10\x03", "physical", 1), (b"\x3e\x80", "functional", 1)]
    cleanup(transport, service)


@pytest.mark.parametrize("payload", ["0e8011100000000000", "999911101000000000", "0e80111010000000"])
def test_denied_wrong_tester_or_incomplete_routing_never_ready(payload):
    bus, transport, service, settings, now = setup()
    service.connect(settings)
    transport.connected = True
    bus.publish(ConnectionEvent(True))
    raw = bytes.fromhex(payload)
    frame = b"\x02\xfd\x00\x06" + len(raw).to_bytes(4, "big") + raw
    bus.publish(RoutingActivationResponseEvent(int.from_bytes(raw[:2], "big"), 0x11, raw[4], True, frame))
    assert service.snapshot.state is SessionState.DISCONNECTING
    assert not service.send(b"\x10\x03")
    assert not service.connect(settings)
    transport.released = True
    service.poll()
    assert service.snapshot.state is SessionState.FAILED
    assert service.snapshot.reason
    cleanup(transport, service)


@pytest.mark.parametrize("phase", ["tcp", "routing"])
def test_deadline_closes_before_allowing_configuration_or_reconnect(phase):
    bus, transport, service, settings, now = setup()
    service.connect(settings)
    if phase == "routing":
        transport.connected = True
        bus.publish(ConnectionEvent(True))
    now[0] = 5.0
    service.poll()
    assert service.snapshot.state is SessionState.DISCONNECTING
    assert "超时" in service.snapshot.reason
    transport.released = True
    service.poll()
    assert service.snapshot.state is SessionState.FAILED
    assert service.connect(settings)
    cleanup(transport, service)


def test_immediate_remote_close_before_queued_success_cannot_ready():
    bus, transport, service, settings, now = setup()
    service.connect(settings)
    transport.connected = True
    bus.publish(ConnectionEvent(True))
    transport.connected = False
    bus.publish(RoutingActivationResponseEvent(0x0E80, 0x11, 0x10, True,
        bytes.fromhex("02fd0006000000090e8011101000000000")))
    assert service.snapshot.state is not SessionState.READY
    assert not service.send(b"\x10\x03")
    cleanup(transport, service)


def test_keep_alive_captures_generation_and_stops_on_disconnect():
    bus, transport, service, settings, now = setup()
    settings = replace(settings, tester_present_interval_ms=10)
    activate(bus, transport, service, settings)
    service.set_keep_alive(True)
    assert transport.sent.wait(1)
    assert transport.sends[0] == (b"\x3e\x80", "functional", 1)
    service.disconnect()
    service.shutdown()
    transport.released = True
    service.poll()
    assert service.snapshot.state is SessionState.DISCONNECTED
    assert not service.send(b"\x10\x03")
    service.close()
    service.close()
    assert all(not subscribers for subscribers in bus.subscribers.values())


def test_close_is_idempotent_and_cancel_ignores_late_errors():
    bus, transport, service, settings, now = setup()
    service.connect(settings)
    service.disconnect()
    bus.publish(ConnectionEvent(True))
    bus.publish(ErrorEvent("old error", "doip-main"))
    assert service.snapshot.state is SessionState.DISCONNECTING
    assert transport.ra_count == 0
    transport.released = True
    service.poll()
    assert service.snapshot.state is SessionState.DISCONNECTED
    service.close()
    service.close()
    assert not service.connect(settings)


def test_transport_disappears_ready_poll_immediately_disables_send():
    bus, transport, service, settings, now = setup()
    activate(bus, transport, service, settings)
    transport.connected = False
    service.poll()
    assert service.snapshot.state is SessionState.DISCONNECTING
    assert not service.send(b"\x10\x03")
    cleanup(transport, service)
