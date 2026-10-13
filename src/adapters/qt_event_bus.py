"""Main-thread Qt dispatch of the 11 known domain events.

Subscriber storage belongs exclusively to the application thread. Worker
publishers only emit the relay; its bound QObject slot receives queued events.
Public signals mirror dispatch for integration, while Port subscribers run
synchronously on the application thread. This is a local P1 implementation.
"""

from collections.abc import Mapping
import threading
from types import MappingProxyType

from PySide6.QtCore import QCoreApplication, QObject, QThread, Qt, Signal, Slot

from src.ports.event_bus import EventBusPort, EventHandler
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


EVENT_SIGNAL_MAP: Mapping[type[DomainEvent], str] = MappingProxyType(
    {
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
        SessionStateChangedEvent: "session_state_changed",
    }
)


class QtDomainEventBus(QObject, EventBusPort):
    connection_changed = Signal(object)
    data_received = Signal(object)
    doip_message_received = Signal(object)
    data_sent = Signal(object)
    routing_activation_response = Signal(object)
    diagnostic_ack = Signal(object)
    error_occurred = Signal(object)
    flash_progress = Signal(object)
    flash_completed = Signal(object)
    log_event = Signal(object)
    can_message_received = Signal(object)
    session_state_changed = Signal(object)
    _relay = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            raise RuntimeError("QtDomainEventBus must be created on the application main thread")
        super().__init__(parent)
        self._owner_ident = threading.get_ident()
        self._subscribers: dict[type[DomainEvent], list[EventHandler]] = {}
        self._closed = False
        self._relay.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    def _require_owner(self) -> None:
        if threading.get_ident() != self._owner_ident:
            raise RuntimeError("Event subscriptions and close belong to the application main thread")

    @staticmethod
    def _require_event_class(event_class: type[DomainEvent]) -> None:
        if event_class not in EVENT_SIGNAL_MAP:
            raise TypeError(f"Unsupported domain event class: {event_class!r}")

    def subscribe(self, event_class: type[DomainEvent], handler: EventHandler) -> None:
        self._require_owner()
        self._require_event_class(event_class)
        if self._closed:
            raise RuntimeError("Cannot subscribe to a closed event bus")
        if not callable(handler):
            raise TypeError("Event handler must be callable")
        handlers = self._subscribers.setdefault(event_class, [])
        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, event_class: type[DomainEvent], handler: EventHandler) -> None:
        self._require_owner()
        self._require_event_class(event_class)
        handlers = self._subscribers.get(event_class)
        if handlers and handler in handlers:
            handlers.remove(handler)
            if not handlers:
                del self._subscribers[event_class]

    def publish(self, event: DomainEvent) -> None:
        self._require_event_class(type(event))
        if threading.get_ident() == self._owner_ident:
            self._dispatch(event)
        else:
            self._relay.emit(event)

    @Slot(object)
    def _dispatch(self, event: DomainEvent) -> None:
        self._require_owner()
        if self._closed:
            return
        event_class = type(event)
        getattr(self, EVENT_SIGNAL_MAP[event_class]).emit(event)
        for handler in tuple(self._subscribers.get(event_class, ())):
            if self._closed:
                break
            handler(event)

    def close(self) -> None:
        """Idempotently release subscribers and discard delayed relay deliveries."""
        self._require_owner()
        self._closed = True
        self._subscribers.clear()
