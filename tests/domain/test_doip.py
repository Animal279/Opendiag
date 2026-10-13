import pytest

from src.domain.connection_models import DoIPSettings
from src.domain.doip import (build_frame, decode_frame, build_routing_activation,
                             build_diagnostic, parse_routing_response)
from src.domain.hex_input import parse_hex
from tests.domain.test_connection_settings import sample_config


def test_independent_routing_and_diagnostic_vectors():
    settings = DoIPSettings.from_config(sample_config())
    assert build_routing_activation(settings).hex() == "02fd00050000000b0e800000000000ffffffff"
    assert build_diagnostic(settings, b"\x10\x03").hex() == "02fd8001000000060e8011101003"
    assert build_diagnostic(settings, b"\x10\x03", "functional").hex() == "02fd8001000000060e80e4001003"
    with pytest.raises(ValueError):
        build_diagnostic(settings, b"", "physical")
    with pytest.raises(ValueError):
        build_diagnostic(settings, b"\x10", "invalid")


@pytest.mark.parametrize("tail", ["", "11223344"])
def test_routing_response_has_independent_complete_layout(tail):
    response = parse_routing_response(bytes.fromhex("0e8011101000000000" + tail))
    assert (response.tester_address, response.entity_address, response.response_code) == (0x0E80, 0x1110, 0x10)


@pytest.mark.parametrize("length", [0, 8, 10, 12, 14])
def test_partial_or_invalid_routing_response_cannot_succeed(length):
    with pytest.raises(ValueError):
        parse_routing_response(b"\0" * length)


def test_complete_uds_and_unknown_payload_are_preserved():
    frame = decode_frame(bytes.fromhex("02fd80010000000a11100e805003003201f4"))
    assert frame.payload[4:] == bytes.fromhex("5003003201f4")
    assert decode_frame(build_frame(0x1234, b"abc")).payload_type == 0x1234


@pytest.mark.parametrize("raw", ["02fe00000000000100", "02fd80010000000a11100e805003", "02fd0000000000010000"])
def test_bad_inverse_and_length_rejected(raw):
    with pytest.raises(ValueError):
        decode_frame(bytes.fromhex(raw))


@pytest.mark.parametrize("text", ["1", "0x10", "GG", "10-03", "", "１２"])
def test_hex_boundary_rejects_invalid_input(text):
    with pytest.raises(ValueError):
        parse_hex(text)


def test_hex_boundary_supports_whitespace_and_explicit_empty():
    assert parse_hex("10\n03\t AB") == b"\x10\x03\xab"
    assert parse_hex("", allow_empty=True) == b""
