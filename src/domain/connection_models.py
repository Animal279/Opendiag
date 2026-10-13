"""Immutable connection parameters and owner-thread session projections."""

from dataclasses import dataclass, fields
from enum import Enum
from ipaddress import IPv4Address

from .hex_input import parse_hex


def _integer(value, name: str, maximum: int, minimum: int = 0) -> int:
    try:
        if isinstance(value, str):
            value = int(value, 16 if value.lower().startswith("0x") else 10)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError(f"{name}: 需要 {minimum}–{maximum} 范围的整数") from None
    return value


@dataclass(frozen=True, slots=True)
class DoIPSettings:
    target_ip: str
    target_port: int
    source_address: int
    target_address: int
    functional_address: int
    protocol_version: int
    activation_type: int
    oem_data: bytes
    connect_timeout_ms: int
    routing_timeout_ms: int
    max_payload_length: int
    tester_present_interval_ms: int

    def __post_init__(self):
        try:
            if not isinstance(self.target_ip, str):
                raise ValueError
            IPv4Address(self.target_ip)
        except ValueError:
            raise ValueError("target_ip: 需要有效的 IPv4 地址") from None
        limits = {"target_port": (1, 65535), "source_address": (0, 65535),
                  "target_address": (0, 65535), "functional_address": (0, 65535),
                  "protocol_version": (0, 255), "activation_type": (0, 255),
                  "connect_timeout_ms": (1, 3600000), "routing_timeout_ms": (1, 3600000),
                  "max_payload_length": (1, 0xFFFFFFFF), "tester_present_interval_ms": (1, 3600000)}
        for name, (minimum, maximum) in limits.items():
            object.__setattr__(self, name, _integer(getattr(self, name), name, maximum, minimum))
        if type(self.oem_data) is not bytes or len(self.oem_data) != 4:
            raise ValueError("oem_data: 需要四个字节")

    @classmethod
    def from_config(cls, config: dict) -> "DoIPSettings":
        if not isinstance(config, dict) or config.get("transport") != "doip":
            raise ValueError("transport: 当前仅支持 doip")
        section = config.get("doip")
        if not isinstance(section, dict):
            raise ValueError("doip: 需要配置对象")
        values = {}
        for field in fields(cls):
            key = {"activation_type": "routing_activation_type", "oem_data": "routing_oem_data"}.get(field.name, field.name)
            if key not in section:
                raise ValueError(f"{key}: 缺少必需配置")
            values[field.name] = section[key]
        try:
            values["oem_data"] = parse_hex(values["oem_data"])
        except ValueError:
            raise ValueError("routing_oem_data: 需要四个十六进制字节") from None
        try:
            return cls(**values)
        except ValueError as exc:
            raise ValueError(str(exc).replace("activation_type:", "routing_activation_type:").replace("oem_data:", "routing_oem_data:")) from None

    def to_config(self) -> dict:
        section = {field.name: getattr(self, field.name) for field in fields(self)}
        section["routing_activation_type"] = section.pop("activation_type")
        section["routing_oem_data"] = section.pop("oem_data").hex(" ").upper()
        return {"transport": "doip", "doip": section}


class SessionState(Enum):
    DISCONNECTED = "未连接"
    CONNECTING = "连接中"
    ACTIVATING = "激活中"
    READY = "已激活"
    DISCONNECTING = "断开中"
    FAILED = "失败"


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    state: SessionState
    generation: int
    reason: str
