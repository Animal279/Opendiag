"""Wire literals independent of production parsing; logs are evidence, not verdicts."""

import pytest


def inspect(data, kind="uds"):
    from src.application.response_inspection import inspect_response
    return inspect_response(bytes.fromhex(data) if isinstance(data, str) else data, kind)


def test_session_response_decodes_server_units_and_preserves_bytes():
    result = inspect("50 03 00 32 01 F4")
    assert not result.error
    assert result.response.service_id == 0x10
    assert result.response.positive
    assert (result.response.timing.session, result.response.timing.p2_ms,
            result.response.timing.p2_star_ms) == (3, 50, 5000)
    assert result.uds == bytes.fromhex("50 03 00 32 01 F4")


@pytest.mark.parametrize("payload", ["50", "50 03", "50 03 00 32", "50 03 00 32 01", "50 03 00 32 01 F4 00"])
def test_incomplete_or_extended_timing_does_not_become_valid_server_parameters(payload):
    result = inspect(payload)
    assert result.error
    assert result.response is None
    assert result.uds == bytes.fromhex(payload)


@pytest.mark.parametrize("payload,nrc", [("7F 22 14", 0x14), ("7F 31 78", 0x78), ("7F 22 AB", 0xAB)])
def test_negative_response_preserves_unknown_codes_and_pending_is_not_success(payload, nrc):
    result = inspect(payload)
    assert not result.error
    assert not result.response.positive
    assert result.response.nrc == nrc
    assert f"0x{nrc:02X}" in result.summary


@pytest.mark.parametrize("payload", [b"", b"\x7f", b"\x7f\x22", b"\x62\xf1", b"\x71\x01\xaa", b"\x59\x04\xc1\x22\x87", b"\x59\x02\xff\xc1"])
def test_short_headers_and_partial_dtc_records_are_visible_errors(payload):
    result = inspect(payload)
    assert result.error and result.raw == payload


def test_dtc_snapshot_reports_status_bits_without_inventing_snapshot_codec():
    before = inspect("59 04 C2 54 87 2B 01 05 D0 01 00 00")
    after = inspect("59 04 C2 54 87 2A 01 05 D0 01 00 00")
    assert "testFailed=1" in "\n".join(before.response.details)
    assert "testFailed=0" in "\n".join(after.response.details)
    assert "confirmedDTC=1" in "\n".join(after.response.details)
    assert "C25487" in "\n".join(after.response.details)
    assert after.uds.endswith(bytes.fromhex("01 05 D0 01 00 00"))


@pytest.mark.parametrize("payload,identifier", [("62 F1 90 41 42", "F190"), ("6E F1 90", "F190"), ("71 01 A1 00 00", "A100")])
def test_identifiers_are_hex_without_guessing_project_payload_encoding(payload, identifier):
    result = inspect(payload)
    assert not result.error
    assert identifier in "\n".join(result.response.details)


def test_doip_diagnostic_frame_extracts_addresses_and_complete_uds():
    result = inspect("02 FD 80 01 00 00 00 0A 11 10 0E 80 50 03 00 32 01 F4", "doip")
    assert not result.error
    assert result.uds == bytes.fromhex("50 03 00 32 01 F4")
    assert "1110" in result.envelope and "0E80" in result.envelope


@pytest.mark.parametrize("frame", ["02 FD 80 01 00 00 00 0A 11 10 0E 80 50 03", "02 FD 80 02 00 00 00 05 11 10 0E 80 00", "02 FD 80 01 00 00 00 04 11 10 0E 80"])
def test_truncated_doip_ack_and_empty_uds_are_not_diagnostic_success(frame):
    result = inspect(frame, "doip")
    assert result.error and result.response is None


def test_unknown_sid_is_not_labeled_positive():
    result = inspect("FF 00")
    assert result.error and result.response is None


def test_large_dtc_response_has_bounded_summary_and_preserves_complete_bytes():
    raw = b"\x59\x02\xff" + bytes.fromhex("C1 22 87 2B") * 262144
    result = inspect(raw)
    assert not result.error and result.uds is raw
    assert "262144" in "\n".join(result.response.details)
    assert len("\n".join(result.response.details)) < 6000


@pytest.mark.parametrize("session", [0, 5, 0x3F, 0x7F, 0x80, 0xFF])
def test_reserved_session_ids_cannot_generate_valid_timing(session):
    result = inspect(bytes([0x50, session, 0, 1, 0, 1]))
    assert result.error and result.response is None


@pytest.mark.parametrize("session", [0x40, 0x5F, 0x60, 0x7E])
def test_manufacturer_and_supplier_session_ranges_remain_inspectable(session):
    result = inspect(bytes([0x50, session, 0, 1, 0, 1]))
    assert not result.error and result.response.timing.session == session


@pytest.mark.parametrize("code,name", [(0x21, "BusyRepeatRequest"), (0x35, "InvalidKey"), (0x73, "WrongBlockSequenceCounter")])
def test_common_nrc_names_are_interpreted_without_altering_codes(code, name):
    result = inspect(bytes([0x7F, 0x27, code]))
    assert result.response.nrc == code
    assert name in "\n".join(result.response.details)
