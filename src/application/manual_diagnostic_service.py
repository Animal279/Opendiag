"""Owner-thread routing lifecycle; accepted actions never imply ECU success."""

from collections.abc import Callable
import threading
import time

from src.domain.doip import PayloadType, decode_frame, parse_routing_response
from src.ports.connection import ConnectionPort
from src.ports.diagnostic import DiagnosticPort
from src.ports.event_bus import EventBusPort
from src.ports.events import (ConnectionEvent, ErrorEvent, RoutingActivationResponseEvent,
                             SessionStateChangedEvent)
from src.ports.manual_diagnostic import ManualDiagnosticPort
from src.ports.model_types import DoIPSettings, SessionSnapshot, SessionState


class ManualDiagnosticService(ManualDiagnosticPort):
    def __init__(self, connection: ConnectionPort, diagnostic: DiagnosticPort,
                 event_bus: EventBusPort, *, clock: Callable[[], float] = time.monotonic):
        self._connection = connection
        self._diagnostic = diagnostic
        self._bus = event_bus
        self._clock = clock
        self._owner = threading.get_ident()
        self._snapshot = SessionSnapshot(SessionState.DISCONNECTED, 0, "")
        self._settings: DoIPSettings | None = None
        self._deadline = 0.0
        self._failure = False
        self._closed = False
        self._keep_stop = threading.Event()
        self._keep_threads: list[threading.Thread] = []
        self._keep_enabled = False
        self._bindings = ((ConnectionEvent, self._on_connection),
                          (RoutingActivationResponseEvent, self._on_routing),
                          (ErrorEvent, self._on_error))
        for cls, handler in self._bindings:
            event_bus.subscribe(cls, handler)

    def _require_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError("Diagnostic session belongs to the owner thread")

    @property
    def snapshot(self):
        self._require_owner()
        return self._snapshot

    @property
    def keep_alive_enabled(self):
        return self._keep_enabled

    def is_quiescent(self):
        self._require_owner()
        return self._connection.is_quiescent() and all(not t.is_alive() for t in self._keep_threads)

    def _set(self, state, reason=""):
        self._snapshot = SessionSnapshot(state, self._connection.generation, reason)
        self._bus.publish(SessionStateChangedEvent(self._snapshot))

    def connect(self, settings):
        self._require_owner()
        if self._closed or self._snapshot.state not in (SessionState.DISCONNECTED, SessionState.FAILED) or not self.is_quiescent():
            return False
        self._settings = settings
        self._failure = False
        self._connection.configure(settings)
        if not self._connection.connect(settings.target_ip, settings.target_port):
            self._set(SessionState.FAILED, "TCP 连接任务未受理")
            return False
        self._deadline = self._clock() + settings.connect_timeout_ms / 1000
        self._set(SessionState.CONNECTING)
        return True

    def _on_connection(self, event):
        if self._closed:
            return
        if event.connected:
            if self._snapshot.state is SessionState.CONNECTING and self._connection.is_connected():
                self._deadline = self._clock() + self._settings.routing_timeout_ms / 1000
                self._set(SessionState.ACTIVATING)
                if not self._connection.send_routing_activation():
                    self._begin_disconnect("路由激活请求未受理", failure=True)
        elif self._snapshot.state in (SessionState.CONNECTING, SessionState.ACTIVATING, SessionState.READY):
            self._begin_disconnect("诊断 TCP 已断开", failure=True)

    def _on_routing(self, event):
        if self._snapshot.state is not SessionState.ACTIVATING:
            return
        try:
            frame = decode_frame(event.raw_data)
            response = parse_routing_response(frame.payload)
            if frame.payload_type != PayloadType.ROUTING_RESPONSE or frame.version != self._settings.protocol_version:
                raise ValueError("路由激活响应类型或版本不匹配")
            if response.tester_address != self._settings.source_address:
                raise ValueError(f"路由激活 Tester 地址不匹配: 0x{response.tester_address:04X}")
            if response.response_code != 0x10:
                raise ValueError(f"路由激活被拒绝: 0x{response.response_code:02X}")
            if not event.is_success or not self._connection.is_connected():
                raise ValueError("路由激活回应到达时 TCP 已关闭")
        except ValueError as exc:
            self._begin_disconnect(str(exc), failure=True)
            return
        self._set(SessionState.READY, f"Entity 0x{response.entity_address:04X}")

    def _on_error(self, event):
        if event.source != "doip-main" or self._closed:
            return
        if self._snapshot.state in (SessionState.CONNECTING, SessionState.ACTIVATING) or (
                self._snapshot.state is SessionState.READY and not self._connection.is_connected()):
            self._begin_disconnect(event.message, failure=True)

    def _begin_disconnect(self, reason="", *, failure=False):
        if self._snapshot.state is SessionState.DISCONNECTING:
            return
        self._keep_stop.set()
        self._keep_enabled = False
        self._failure = failure
        self._set(SessionState.DISCONNECTING, reason)
        self._connection.disconnect()

    def disconnect(self):
        self._require_owner()
        if self._snapshot.state not in (SessionState.DISCONNECTED, SessionState.FAILED, SessionState.DISCONNECTING):
            self._begin_disconnect()

    def send(self, data, addressing="physical"):
        self._require_owner()
        if self._closed or self._snapshot.state is not SessionState.READY or not self._connection.is_connected():
            return False
        accepted = self._diagnostic.send_diagnostic_message(data, addressing, generation=self._snapshot.generation)
        if not accepted:
            self._bus.publish(ErrorEvent("UDS 发送未受理，请检查输入或连接状态", "manual-diagnostic"))
        return accepted

    def set_keep_alive(self, enabled):
        self._require_owner()
        if not enabled:
            self._keep_stop.set()
            self._keep_enabled = False
            return
        if self._closed or self._keep_enabled or self._snapshot.state is not SessionState.READY:
            return
        stop = threading.Event()
        self._keep_stop = stop
        self._keep_enabled = True
        interval = self._settings.tester_present_interval_ms / 1000
        generation = self._snapshot.generation
        diagnostic = self._diagnostic
        # The worker reads only captured immutable parameters and its own Event.
        def work():
            while not stop.wait(interval):
                if not diagnostic.send_diagnostic_message(b"\x3e\x80", "functional", generation=generation):
                    break
        thread = threading.Thread(target=work, name="diagnostic-keep-alive", daemon=True)
        self._keep_threads.append(thread)
        thread.start()

    def poll(self):
        self._require_owner()
        self._connection.poll()
        self._keep_threads[:] = [thread for thread in self._keep_threads if thread.is_alive()]
        state = self._snapshot.state
        if state in (SessionState.CONNECTING, SessionState.ACTIVATING) and self._clock() >= self._deadline:
            self._begin_disconnect("TCP 连接超时" if state is SessionState.CONNECTING else "路由激活超时", failure=True)
        elif state is SessionState.READY and not self._connection.is_connected():
            self._begin_disconnect("诊断 TCP 已断开", failure=True)
        elif state is SessionState.DISCONNECTING and self.is_quiescent():
            self._set(SessionState.FAILED if self._failure else SessionState.DISCONNECTED, self._snapshot.reason)

    def close(self):
        self._require_owner()
        if self._closed:
            return
        self.disconnect()
        self._keep_stop.set()
        self._closed = True
        for cls, handler in self._bindings:
            self._bus.unsubscribe(cls, handler)

    def shutdown(self):
        self._require_owner()
        self._keep_stop.set()
        for thread in tuple(self._keep_threads):
            thread.join(timeout=2)
        if any(t.is_alive() for t in self._keep_threads):
            raise RuntimeError("Diagnostic keep-alive worker did not stop")
