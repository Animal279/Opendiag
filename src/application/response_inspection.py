"""Stateless local inspection; does not send, correlate requests or alter timers."""

from dataclasses import dataclass

from src.domain.doip import PayloadType, decode_frame
from src.domain.uds_response import SERVICE_NAMES, UdsResponse, parse_uds_response


@dataclass(frozen=True, slots=True)
class ResponseInspection:
    raw: bytes
    uds: bytes | None
    response: UdsResponse | None
    summary: str
    envelope: str = ""
    error: str = ""


def inspect_response(data: bytes, kind: str = "uds") -> ResponseInspection:
    uds, envelope = data, ""
    try:
        if not isinstance(data, bytes):
            raise ValueError("输入需要 bytes")
        if kind == "doip":
            uds = None
            frame = decode_frame(data)
            if frame.payload_type != PayloadType.DIAGNOSTIC:
                raise ValueError("当前帧不是 DoIP 诊断报文 0x8001；ACK/NACK 不作为 UDS 响应解析")
            if len(frame.payload) <= 4:
                raise ValueError("DoIP 诊断帧缺少完整地址或非空 UDS 数据")
            envelope = f"DoIP 0x{frame.version:02X} / SA {frame.payload[:2].hex().upper()} / TA {frame.payload[2:4].hex().upper()}"
            uds = frame.payload[4:]
        elif kind != "uds":
            raise ValueError("解析类型需要 uds 或 doip")
        response = parse_uds_response(uds)
    except ValueError as exc:
        return ResponseInspection(data, uds, None, "无法解析响应", envelope, str(exc))
    name = SERVICE_NAMES.get(response.service_id, "未知服务")
    summary = f"{name} 0x{response.service_id:02X} / {'正响应' if response.positive else f'负响应 NRC 0x{response.nrc:02X}'}"
    return ResponseInspection(data, uds, response, summary, envelope)


def inspection_text(result: ResponseInspection) -> str:
    """Bound conversion before hex, while raw/UDS bytes remain complete."""
    data = result.uds if result.uds is not None else result.raw
    preview = data[:171].hex(" ").upper() + (" …" if len(data) > 171 else "")
    lines = [result.envelope, result.summary, result.error]
    if result.response:
        lines.extend(result.response.details)
    lines.extend((f"{len(data)} 字节", preview))
    return "\n".join(line for line in lines if line)
