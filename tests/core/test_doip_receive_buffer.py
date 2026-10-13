import pytest

from src.core.doip_receive_buffer import DoIPReceiveBuffer

RA = bytes.fromhex("02fd0006000000090e8011101000000000")
UDS = bytes.fromhex("02fd80010000000a11100e805003003201f4")


@pytest.mark.parametrize("split", range(1, len(RA + UDS)))
def test_arbitrary_split_and_coalesced_frames(split):
    buffer = DoIPReceiveBuffer(100)
    output = []
    for chunk in ((RA + UDS)[:split], (RA + UDS)[split:]):
        buffer.feed(chunk)
        while (frame := buffer.try_extract()) is not None:
            output.append(frame)
    assert output == [RA, UDS]
    assert buffer.pending_bytes == b""


@pytest.mark.parametrize("bad", [bytes.fromhex("02fe000000000000"), bytes.fromhex("02fd8001ffffffff")])
def test_invalid_header_reports_error_and_resynchronizes(bad):
    buffer = DoIPReceiveBuffer(100)
    buffer.feed(bad + RA)
    assert buffer.try_extract() == RA
    assert buffer.take_errors()
    assert buffer.take_errors() == []
    assert len(buffer.pending_bytes) <= 7


def test_half_frame_is_not_success():
    buffer = DoIPReceiveBuffer(100)
    buffer.feed(RA[:-1])
    assert buffer.try_extract() is None
    assert buffer.pending_bytes == RA[:-1]
