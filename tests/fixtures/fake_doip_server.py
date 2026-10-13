"""A single-connection, queued-response TCP fixture, not an ECU emulator.

The worker owns its receive buffer and socket IO. The Condition protects the
response queue, received snapshots and connection/error state; the stop Event
and finite socket timeout let cleanup interrupt either accept or recv.
"""

from collections import deque
import socket
import struct
import threading
from types import TracebackType


class FakeDoIPServer:
    """Send at most one explicitly queued bytes response per complete request.

    Framing uses the DoIP 8-byte header length. This fixture does not validate
    UDS, route activation, security or protocol responses. The 1 MiB default
    limit protects test-process memory only; it is not a production limit.
    """

    def __init__(self, *, max_payload_length: int = 1024 * 1024) -> None:
        if type(max_payload_length) is not int or max_payload_length < 0:
            raise ValueError("max_payload_length must be a non-negative integer")
        self.max_payload_length = max_payload_length
        self._condition = threading.Condition()
        self._stop_requested = threading.Event()
        self._stopped = threading.Event()
        self._responses: deque[tuple[bytes, tuple[int, ...], bool, threading.Event | None]] = deque()
        self._received: list[bytes] = []
        self._listener: socket.socket | None = None
        self._client: socket.socket | None = None
        self._worker: threading.Thread | None = None
        self._address: tuple[str, int] | None = None
        self._connected = False
        self._error: Exception | None = None

    @property
    def address(self) -> tuple[str, int]:
        with self._condition:
            if self._address is None:
                raise RuntimeError("server has not started")
            return self._address

    @property
    def port(self) -> int:
        return self.address[1]

    @property
    def received(self) -> tuple[bytes, ...]:
        with self._condition:
            return tuple(self._received)

    @property
    def error(self) -> Exception | None:
        with self._condition:
            return self._error

    @property
    def worker(self) -> threading.Thread | None:
        with self._condition:
            return self._worker

    @property
    def closed(self) -> bool:
        with self._condition:
            sockets_closed = all(
                resource is None or resource.fileno() == -1
                for resource in (self._listener, self._client)
            )
            return self._stopped.is_set() and sockets_closed

    def queue_response(self, response: bytes, *, chunks: tuple[int, ...] = (), close_after: bool = False, reply_gate: threading.Event | None = None) -> None:
        if not isinstance(response, bytes):
            raise TypeError("response must be bytes")
        with self._condition:
            self._responses.append((response, chunks, close_after, reply_gate))

    def start(self) -> "FakeDoIPServer":
        with self._condition:
            if self._worker is not None or self._stop_requested.is_set():
                raise RuntimeError("a server instance can only be started once")
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                listener.settimeout(0.1)
            except BaseException:
                listener.close()
                raise
            self._listener = listener
            host, port = listener.getsockname()
            self._address = (host, port)
            self._worker = threading.Thread(
                target=self._run, name="fake-doip-server", daemon=True
            )
            self._worker.start()
        return self

    def wait_for_connection(self, timeout: float = 1.0) -> bool:
        with self._condition:
            self._condition.wait_for(
                lambda: self._connected or self._stopped.is_set(), timeout=timeout
            )
            return self._connected

    def wait_for_received(self, count: int, timeout: float = 1.0) -> bool:
        with self._condition:
            self._condition.wait_for(
                lambda: len(self._received) >= count or self._stopped.is_set(),
                timeout=timeout,
            )
            return len(self._received) >= count

    def wait_for_stopped(self, timeout: float = 1.0) -> bool:
        return self._stopped.wait(timeout)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_requested.set()
        with self._condition:
            resources = (self._client, self._listener)
            worker = self._worker
        for resource in resources:
            self._close_socket(resource)
        if worker is not None:
            worker.join(timeout)
            if worker.is_alive():
                raise RuntimeError("fake DoIP server worker did not stop")
        else:
            self._stopped.set()
        with self._condition:
            self._condition.notify_all()

    @staticmethod
    def _close_socket(resource: socket.socket | None) -> None:
        if resource is None:
            return
        try:
            resource.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        resource.close()

    def _run(self) -> None:
        listener = self._listener
        client: socket.socket | None = None
        try:
            assert listener is not None
            while not self._stop_requested.is_set():
                try:
                    client, _ = listener.accept()
                    break
                except socket.timeout:
                    continue
            if client is None:
                return
            with self._condition:
                self._client = client
                self._connected = True
                self._condition.notify_all()
            client.settimeout(0.1)
            buffer = bytearray()
            while not self._stop_requested.is_set():
                try:
                    chunk = client.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buffer.extend(chunk)
                while len(buffer) >= 8:
                    payload_length = struct.unpack_from("!I", buffer, 4)[0]
                    if payload_length > self.max_payload_length:
                        raise ValueError("request exceeds test-only payload limit")
                    frame_length = 8 + payload_length
                    if len(buffer) < frame_length:
                        break
                    frame = bytes(buffer[:frame_length])
                    del buffer[:frame_length]
                    with self._condition:
                        self._received.append(frame)
                        response = self._responses.popleft() if self._responses else None
                        self._condition.notify_all()
                    if response is not None:
                        data, chunks, close_after, gate = response
                        if gate is not None:
                            while not gate.wait(0.05):
                                if self._stop_requested.is_set():
                                    return
                        offset = 0
                        for size in chunks:
                            client.sendall(data[offset:offset + size])
                            offset += size
                        if offset < len(data):
                            client.sendall(data[offset:])
                        if close_after:
                            return
        except Exception as error:
            if not self._stop_requested.is_set():
                with self._condition:
                    self._error = error
        finally:
            self._close_socket(client)
            self._close_socket(listener)
            self._stopped.set()
            with self._condition:
                self._condition.notify_all()

    def __enter__(self) -> "FakeDoIPServer":
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
