import json
from pathlib import Path
from dataclasses import FrozenInstanceError, replace

import pytest

from src.domain.connection_models import DoIPSettings


def sample_config():
    """Fresh synthetic data; independent of ignored workstation configuration."""
    path = Path(__file__).resolve().parents[2] / "examples/projects/LoopbackDemo/config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_settings_are_validated_and_immutable():
    settings = DoIPSettings.from_config(sample_config())
    assert (settings.target_ip, settings.target_port, settings.source_address,
            settings.target_address, settings.functional_address,
            settings.protocol_version) == ("127.0.0.1", 13400, 0x0E80, 0x1110, 0xE400, 2)
    with pytest.raises(FrozenInstanceError):
        settings.target_ip = "127.0.0.1"
    with pytest.raises(ValueError, match="target_port"):
        replace(settings, target_port=True)


@pytest.mark.parametrize("field,value", [
    ("target_ip", "localhost"), ("target_ip", "300.1.1.1"),
    ("target_port", 0), ("target_port", 65536), ("target_port", True),
    ("source_address", -1), ("target_address", 65536),
    ("functional_address", "0xZZ"), ("protocol_version", 256),
    ("routing_activation_type", False), ("routing_oem_data", "FFFFFF"),
    ("connect_timeout_ms", 0), ("routing_timeout_ms", float("inf")),
    ("max_payload_length", 0), ("tester_present_interval_ms", -1)])
def test_invalid_fields_do_not_fall_back(field, value):
    config = sample_config()
    config["doip"][field] = value
    with pytest.raises(ValueError, match=field):
        DoIPSettings.from_config(config)


def test_missing_required_field_and_unsupported_transport_are_rejected():
    config = sample_config()
    config["transport"] = "docan"
    with pytest.raises(ValueError, match="transport"):
        DoIPSettings.from_config(config)
    config = sample_config()
    del config["doip"]["target_address"]
    with pytest.raises(ValueError, match="target_address"):
        DoIPSettings.from_config(config)
