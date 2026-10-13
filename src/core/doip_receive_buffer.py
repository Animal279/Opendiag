"""Reader-owned incremental TCP framing with bounded header resynchronization."""

import struct


class DoIPReceiveBuffer:
    def __init__(self, max_payload_length: int):
        if type(max_payload_length) is not int or max_payload_length < 1:
            raise ValueError("max_payload_length must be positive")
        self._limit = max_payload_length
        self._buffer = bytearray()
        self._errors: list[str] = []

    def feed(self, data: bytes) -> None:
        self._buffer.extend(data)

    @property
    def pending_bytes(self) -> bytes:
        return bytes(self._buffer)

    def take_errors(self) -> list[str]:
        errors, self._errors = self._errors, []
        return errors

    def try_extract(self) -> bytes | None:
        offset = 0
        while len(self._buffer) - offset >= 8:
            version, inverse, _, length = struct.unpack_from("!BBHI", self._buffer, offset)
            if inverse != version ^ 255 or length > self._limit:
                offset += 1
                continue
            if offset:
                del self._buffer[:offset]
                self._errors.append(f"DoIP 非法头或超长声明，已跳过 {offset} 字节")
            total = 8 + length
            if len(self._buffer) < total:
                return None
            frame = bytes(self._buffer[:total])
            del self._buffer[:total]
            return frame
        if offset:
            del self._buffer[:offset]
            self._errors.append(f"DoIP 非法头或超长声明，已跳过 {offset} 字节")
        return None
