"""Immutable events using the 11 known migration-document payloads.

These are local provisional contracts, not copies of complete original
constructors. Required payload fields come from docs/api-reference.md; the
keyword-only timestamp preserves a supplied source time or defaults to time.time.
"""

from dataclasses import dataclass, field
import time

from .connection_models import SessionSnapshot


@dataclass(frozen=True, slots=True)
class DomainEvent:
    timestamp: float = field(default_factory=time.time, kw_only=True)


@dataclass(frozen=True, slots=True)
class ConnectionEvent(DomainEvent):
    connected: bool


@dataclass(frozen=True, slots=True)
class DataReceivedEvent(DomainEvent):
    data: bytes


@dataclass(frozen=True, slots=True)
class DoIPMessageReceivedEvent(DomainEvent):
    raw_message: bytes
    payload_type: int


@dataclass(frozen=True, slots=True)
class DataSentEvent(DomainEvent):
    """Sending started: full DoIP frame or full unsegmented DoCAN UDS request."""

    data: bytes


@dataclass(frozen=True, slots=True)
class RoutingActivationResponseEvent(DomainEvent):
    """Keep known legacy fields without deciding routing-success policy here."""

    source_addr: int
    activation_type: int
    response_code: int
    is_success: bool
    raw_data: bytes


@dataclass(frozen=True, slots=True)
class DiagnosticAckEvent(DomainEvent):
    is_positive: bool
    ack_code: int
    raw_data: bytes


@dataclass(frozen=True, slots=True)
class ErrorEvent(DomainEvent):
    message: str
    source: str


@dataclass(frozen=True, slots=True)
class FlashProgressEvent(DomainEvent):
    current_block: int
    total_blocks: int
    current_size: int
    total_size: int
    status: str
    progress_percent: float


@dataclass(frozen=True, slots=True)
class FlashCompletedEvent(DomainEvent):
    success: bool
    message: str


@dataclass(frozen=True, slots=True)
class LogEvent(DomainEvent):
    level: str
    data: bytes | None
    description: str


@dataclass(frozen=True, slots=True)
class CanMessageReceivedEvent(DomainEvent):
    can_id: int
    data: bytes
    is_extended: bool
    is_canfd: bool
    channel: int


@dataclass(frozen=True, slots=True)
class SessionStateChangedEvent(DomainEvent):
    snapshot: SessionSnapshot


__all__ = [
    "DomainEvent",
    "ConnectionEvent",
    "DataReceivedEvent",
    "DoIPMessageReceivedEvent",
    "DataSentEvent",
    "RoutingActivationResponseEvent",
    "DiagnosticAckEvent",
    "ErrorEvent",
    "FlashProgressEvent",
    "FlashCompletedEvent",
    "LogEvent",
    "CanMessageReceivedEvent",
    "SessionStateChangedEvent",
]
