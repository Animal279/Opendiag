"""Check source timestamps and immutable payload contracts without Qt."""

from dataclasses import FrozenInstanceError
import time

import pytest

from src.domain.events import DataReceivedEvent, DataSentEvent, LogEvent
from src.ports.events import DataReceivedEvent as PortDataReceivedEvent


def test_timestamp_is_generated_at_construction_and_source_time_is_preserved():
    before = time.time()
    event = DataReceivedEvent(data=b"\x62\xf1\x90")
    after = time.time()
    assert before <= event.timestamp <= after
    assert DataReceivedEvent(data=b"\x62", timestamp=123.25).timestamp == 123.25


def test_payload_and_timestamp_are_immutable():
    event = DataSentEvent(data=b"\x22\xf1\x90", timestamp=42.0)
    with pytest.raises(FrozenInstanceError):
        event.data = b"\x10\x03"
    with pytest.raises(FrozenInstanceError):
        event.timestamp = 43.0


def test_payload_is_required_and_timestamp_is_keyword_only():
    with pytest.raises(TypeError):
        DataReceivedEvent()
    with pytest.raises(TypeError):
        DataReceivedEvent(b"\x62", 42.0)


def test_ports_reexport_identity_and_log_can_have_no_binary_payload():
    assert PortDataReceivedEvent is DataReceivedEvent
    event = LogEvent(level="INFO", data=None, description="应用初始化")
    assert event.data is None
