"""Unique bound QObject receiver for all diagnostic MAIN protocol signals."""

from PySide6.QtCore import QObject, Qt, Slot

from src.core.doip_protocol import DoIPProtocol
from src.domain.doip import PayloadType, build_diagnostic, build_routing_activation, decode_frame, parse_routing_response
from src.ports.connection import ConnectionPort
from src.ports.diagnostic import DiagnosticPort
from src.ports.events import (ConnectionEvent, DataReceivedEvent, DataSentEvent,
                             DiagnosticAckEvent, DoIPMessageReceivedEvent, ErrorEvent,
                             LogEvent, RoutingActivationResponseEvent)


class DoIPAdapter(QObject, ConnectionPort, DiagnosticPort):
    def __init__(self, protocol: DoIPProtocol, event_bus):
        super().__init__()
        self._protocol = protocol
        self._bus = event_bus
        self._settings = None
        self._closed = False
        for signal, handler in self._bindings():
            signal.connect(handler, Qt.ConnectionType.QueuedConnection)

    def _bindings(self):
        return ((self._protocol.connection_changed, self._connection),
                (self._protocol.frame_received, self._receive),
                (self._protocol.incomplete_received, self._incomplete),
                (self._protocol.sending, self._sent),
                (self._protocol.error_occurred, self._error))

    @property
    def generation(self): return self._protocol.generation
    def is_connected(self): return self._protocol.is_connected()
    def is_quiescent(self): return self._protocol.is_quiescent()

    def configure(self, settings):
        if not self.is_quiescent():
            raise RuntimeError("诊断连接尚未释放")
        self._settings = settings

    def connect(self, ip, port):
        if self._closed or self._settings is None or (ip, port) != (self._settings.target_ip, self._settings.target_port):
            return False
        try:
            self._protocol.connect_to(self._settings)
            return True
        except RuntimeError:
            return False

    def disconnect(self): self._protocol.disconnect()
    def poll(self): self._protocol.poll()
    def send_routing_activation(self):
        return self._settings is not None and self._protocol.send(build_routing_activation(self._settings), generation=self.generation)

    def send_diagnostic_message(self, data, addressing="physical", *, generation=None):
        if self._settings is None:
            return False
        try:
            raw = build_diagnostic(self._settings, data, addressing)
        except ValueError:
            return False
        return self._protocol.send(raw, generation=self.generation if generation is None else generation)

    def _valid(self, generation): return not self._closed and generation == self.generation

    @Slot(int, bool, float)
    def _connection(self, generation, connected, stamp):
        if self._valid(generation) and (not connected or self.is_connected()):
            self._bus.publish(ConnectionEvent(connected, timestamp=stamp))

    @Slot(int, bytes, float)
    def _sent(self, generation, data, stamp):
        if self._valid(generation):
            self._bus.publish(DataSentEvent(data, timestamp=stamp))
            self._bus.publish(LogEvent("TX", data, "MAIN DoIP 写出开始", timestamp=stamp))

    @Slot(int, str, float)
    def _error(self, generation, message, stamp):
        if self._valid(generation):
            self._bus.publish(ErrorEvent(message, "doip-main", timestamp=stamp))
            self._bus.publish(LogEvent("ERROR", None, message, timestamp=stamp))

    @Slot(int, bytes, float)
    def _incomplete(self, generation, data, stamp):
        if self._valid(generation):
            self._bus.publish(LogEvent("WARN", data, f"MAIN DoIP 未完成帧 {len(data)}B", timestamp=stamp))

    @Slot(int, bytes, float)
    def _receive(self, generation, raw, stamp):
        if not self._valid(generation):
            return
        frame = decode_frame(raw)
        payload = frame.payload
        kind = frame.payload_type
        description = f"MAIN DoIP 0x{kind:04X}"
        if kind == PayloadType.DIAGNOSTIC and len(payload) > 4:
            description += " / UDS"
            if len(payload) >= 7 and payload[4] == 0x7F:
                code = payload[6]
                meaning = {0x14: "ResponseTooLong", 0x78: "ResponsePending"}.get(code, "Unknown NRC")
                description += f" NRC 0x{code:02X} {meaning}"
        elif kind in (PayloadType.DIAGNOSTIC_ACK, PayloadType.DIAGNOSTIC_NACK) and len(payload) >= 5:
            description += f" {'ACK' if kind == PayloadType.DIAGNOSTIC_ACK else 'NACK'} 0x{payload[4]:02X}"
        elif kind == PayloadType.GENERIC_NACK and payload:
            description += f" 通用 NACK 0x{payload[0]:02X}"
        self._bus.publish(DoIPMessageReceivedEvent(raw, kind, timestamp=stamp))
        self._bus.publish(LogEvent("RX", raw, description, timestamp=stamp))
        if frame.version != self._settings.protocol_version:
            self._error(generation, f"DoIP 版本不匹配: 0x{frame.version:02X}", stamp)
            return
        if kind == PayloadType.ROUTING_RESPONSE:
            try:
                response = parse_routing_response(payload)
            except ValueError as exc:
                self._error(generation, str(exc), stamp)
                return
            valid = response.tester_address == self._settings.source_address
            self._bus.publish(RoutingActivationResponseEvent(
                response.tester_address, payload[2], response.response_code,
                valid and response.response_code == 0x10 and self.is_connected(), raw, timestamp=stamp))
        elif kind == PayloadType.DIAGNOSTIC and len(payload) > 4:
            source, target = int.from_bytes(payload[:2], "big"), int.from_bytes(payload[2:4], "big")
            if source == self._settings.target_address and target == self._settings.source_address:
                self._bus.publish(DataReceivedEvent(payload[4:], timestamp=stamp))
        elif kind in (PayloadType.DIAGNOSTIC_ACK, PayloadType.DIAGNOSTIC_NACK) and len(payload) >= 5:
            self._bus.publish(DiagnosticAckEvent(kind == PayloadType.DIAGNOSTIC_ACK, payload[4], raw, timestamp=stamp))

    def shutdown(self):
        if not self._closed:
            self._closed = True
            for signal, handler in self._bindings():
                signal.disconnect(handler)
        self._protocol.shutdown()
