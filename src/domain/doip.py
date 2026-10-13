"""Pure DoIP wire codecs; no transport or Qt dependencies."""

from dataclasses import dataclass
from enum import IntEnum
import struct

from .connection_models import DoIPSettings, _integer


class PayloadType(IntEnum):
    GENERIC_NACK = 0x0000
    ROUTING_REQUEST = 0x0005
    ROUTING_RESPONSE = 0x0006
    ALIVE_REQUEST = 0x0007
    ALIVE_RESPONSE = 0x0008
    DIAGNOSTIC = 0x8001
    DIAGNOSTIC_ACK = 0x8002
    DIAGNOSTIC_NACK = 0x8003


@dataclass(frozen=True, slots=True)
class DoIPFrame:
    version: int
    payload_type: int
    payload: bytes


@dataclass(frozen=True, slots=True)
class RoutingResponse:
    tester_address: int
    entity_address: int
    response_code: int


def build_frame(payload_type: int, payload: bytes, version: int = 2) -> bytes:
    if type(payload) is not bytes:
        raise ValueError("payload must be bytes")
    version = _integer(version, "version", 255)
    payload_type = _integer(int(payload_type) if isinstance(payload_type, PayloadType) else payload_type, "payload_type", 65535)
    return struct.pack("!BBHI", version, version ^ 255, payload_type, len(payload)) + payload


def decode_frame(raw: bytes) -> DoIPFrame:
    if not isinstance(raw, bytes) or len(raw) < 8:
        raise ValueError("Incomplete DoIP header")
    version, inverse, payload_type, length = struct.unpack("!BBHI", raw[:8])
    if inverse != version ^ 255 or len(raw) != length + 8:
        raise ValueError("Invalid DoIP inverse version or payload length")
    return DoIPFrame(version, payload_type, raw[8:])


def build_routing_activation(settings: DoIPSettings) -> bytes:
    payload = struct.pack("!HB", settings.source_address, settings.activation_type) + b"\0" * 4 + settings.oem_data
    return build_frame(PayloadType.ROUTING_REQUEST, payload, settings.protocol_version)


def build_diagnostic(settings: DoIPSettings, data: bytes, addressing: str = "physical") -> bytes:
    if addressing not in {"physical", "functional"} or type(data) is not bytes or not data:
        raise ValueError("Diagnostic message requires nonempty bytes and physical/functional addressing")
    target = settings.target_address if addressing == "physical" else settings.functional_address
    payload = struct.pack("!HH", settings.source_address, target) + data
    if len(payload) > settings.max_payload_length:
        raise ValueError("Diagnostic payload exceeds max_payload_length")
    return build_frame(PayloadType.DIAGNOSTIC, payload, settings.protocol_version)


def parse_routing_response(payload: bytes) -> RoutingResponse:
    if len(payload) not in (9, 13):
        raise ValueError("Routing response must have a complete 9 or 13 byte payload")
    return RoutingResponse(*struct.unpack("!HHB", payload[:5]))
