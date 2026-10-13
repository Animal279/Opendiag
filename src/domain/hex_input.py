"""Strict hexadecimal conversion at text boundaries."""

import re


def parse_hex(text: str, *, allow_empty: bool = False) -> bytes:
    if not isinstance(text, str):
        raise ValueError("Hex input must be text")
    compact = "".join(text.split())
    if not compact and allow_empty:
        return b""
    if not compact or len(compact) % 2 or re.fullmatch(r"[0-9a-fA-F]+", compact) is None:
        raise ValueError("请输入完整的十六进制字节（例如 10 03）")
    return bytes.fromhex(compact)
