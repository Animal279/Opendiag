"""Exercise fixed signal mapping, main-thread relay and lifecycle boundaries."""

import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Slot
from PySide6.QtTest import QSignalSpy

from src.adapters.qt_event_bus import EVENT_SIGNAL_MAP, QtDomainEventBus
from src.ports.events import (
    CanMessageReceivedEvent,
    ConnectionEvent,
    DataReceivedEvent,
    DataSentEvent,
    DiagnosticAckEvent,
    DoIPMessageReceivedEvent,
    DomainEvent,
    ErrorEvent,
    FlashCompletedEvent,
    FlashProgressEvent,
    LogEvent,
    RoutingActivationResponseEvent,
    SessionStateChangedEvent,
)
from src.ports.model_types import SessionSnapshot, SessionState


def run_worker(action):
    errors = []

    def work():
        try:
            action()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive(), "Event worker did not exit"
    return errors


class Receiver(QObject):
    def __init__(self):
        super().__init__()
        self.received = []
        self.thread_idents = []
        self.qt_threads = []

    @Slot(object)
    def on_event(self, event):
        self.received.append(event)
        self.thread_idents.append(threading.get_ident())
        self.qt_threads.append(QThread.currentThread())


def test_all_11_mappings_emit_only_their_own_signal_synchronously(qapp):
    expected = {
        ConnectionEvent: "connection_changed",
        DataReceivedEvent: "data_received",
        DoIPMessageReceivedEvent: "doip_message_received",
        DataSentEvent: "data_sent",
        RoutingActivationResponseEvent: "routing_activation_response",
        DiagnosticAckEvent: "diagnostic_ack",
        ErrorEvent: "error_occurred",
        FlashProgressEvent: "flash_progress",
        FlashCompletedEvent: "flash_completed",
        LogEvent: "log_event",
        CanMessageReceivedEvent: "can_message_received",
    }
    assert dict(list(EVENT_SIGNAL_MAP.items())[:11]) == expected
    assert list(EVENT_SIGNAL_MAP)[11:] == [SessionStateChangedEvent]
    events = [
        ConnectionEvent(connected=True),
        DataReceivedEvent(data=b"\x62\xf1\x90"),
        DoIPMessageReceivedEvent(raw_message=b"\x02\xfd", payload_type=0x8001),
        DataSentEvent(data=b"\x22\xf1\x90"),
        RoutingActivationResponseEvent(0x0E80, 0x10, 0x10, True, b"\x10"),
        DiagnosticAckEvent(True, 0, b"\x00"),
        ErrorEvent(message="发送失败", source="doip"),
        FlashProgressEvent(1, 2, 16, 32, "下载", 50.0),
        FlashCompletedEvent(success=False, message="中断"),
        LogEvent(level="WARN", data=None, description="未加载项目"),
        CanMessageReceivedEvent(0x123, b"\x01", False, False, 0),
    ]
    bus = QtDomainEventBus()
    spies = {cls: QSignalSpy(getattr(bus, name)) for cls, name in expected.items()}
    received = []
    for event_class in expected:
        bus.subscribe(event_class, received.append)
    for index, event in enumerate(events):
        bus.publish(event)
        assert received[-1] is event
        assert [spy.count() for spy in spies.values()] == [
            1 if position <= index else 0 for position in range(11)
        ]
        assert spies[type(event)].at(0)[0] is event
    bus.close()


def test_worker_publish_is_queued_to_main_thread_and_preserves_event(qapp):
    bus = QtDomainEventBus()
    receiver = Receiver()
    bus.subscribe(DataReceivedEvent, receiver.on_event)
    spy = QSignalSpy(bus.data_received)
    event = DataReceivedEvent(data=b"\x62\xf1\x90", timestamp=123.5)
    assert run_worker(lambda: bus.publish(event)) == []
    assert receiver.received == []
    assert spy.wait(1000)
    assert receiver.received == [event]
    assert receiver.thread_idents == [threading.get_ident()]
    assert receiver.qt_threads == [qapp.thread()]
    assert receiver.received[0].timestamp == 123.5
    bus.close()


def test_duplicate_subscription_is_idempotent_and_unsubscribe_removes_handler(qapp):
    bus = QtDomainEventBus()
    received = []
    handler = received.append
    bus.subscribe(ConnectionEvent, handler)
    bus.subscribe(ConnectionEvent, handler)
    bus.publish(ConnectionEvent(True))
    assert len(received) == 1
    bus.unsubscribe(ConnectionEvent, handler)
    bus.unsubscribe(ConnectionEvent, handler)
    bus.publish(ConnectionEvent(False))
    assert len(received) == 1
    bus.close()


def test_close_drops_queued_and_future_events(qapp):
    bus = QtDomainEventBus()
    received = []
    bus.subscribe(ConnectionEvent, received.append)
    spy = QSignalSpy(bus.connection_changed)
    assert run_worker(lambda: bus.publish(ConnectionEvent(True))) == []
    bus.close()
    bus.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
    assert run_worker(lambda: bus.publish(ConnectionEvent(False))) == []
    QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
    bus.publish(ConnectionEvent(False))
    assert received == []
    assert spy.count() == 0
    with pytest.raises(RuntimeError, match="closed"):
        bus.subscribe(ConnectionEvent, received.append)


def test_subscription_and_close_cannot_mutate_bus_from_worker(qapp):
    bus = QtDomainEventBus()
    received = []
    bus.subscribe(ConnectionEvent, received.append)
    for action in (
        lambda: bus.subscribe(ConnectionEvent, received.append),
        lambda: bus.unsubscribe(ConnectionEvent, received.append),
        bus.close,
    ):
        errors = run_worker(action)
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)
    bus.publish(ConnectionEvent(True))
    assert len(received) == 1
    bus.close()


def test_constructor_requires_application_main_thread(qapp):
    errors = run_worker(QtDomainEventBus)
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)


def test_unknown_event_cannot_bypass_fixed_mapping(qapp):
    bus = QtDomainEventBus()
    with pytest.raises(TypeError, match="Unsupported"):
        bus.publish(DomainEvent())
    with pytest.raises(TypeError, match="Unsupported"):
        bus.subscribe(DomainEvent, lambda event: None)
    bus.close()


def test_session_state_is_queued_and_discarded_after_close(qapp):
    bus = QtDomainEventBus()
    receiver = Receiver()
    bus.subscribe(SessionStateChangedEvent, receiver.on_event)
    event = SessionStateChangedEvent(SessionSnapshot(SessionState.READY, 3, ""))
    assert run_worker(lambda: bus.publish(event)) == []
    spy = QSignalSpy(bus.session_state_changed)
    assert spy.wait(1000)
    assert receiver.received == [event]
    assert receiver.thread_idents == [threading.get_ident()]
    assert run_worker(lambda: bus.publish(event)) == []
    bus.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
    assert receiver.received == [event]
