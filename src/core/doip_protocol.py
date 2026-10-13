"""Single diagnostic TCP lifecycle. All socket IO belongs to daemon workers."""

from dataclasses import dataclass, field
import socket
import threading
import time

from PySide6.QtCore import QObject, Signal

from src.domain.connection_models import DoIPSettings
from src.domain.doip import PayloadType, build_frame, decode_frame
from .doip_receive_buffer import DoIPReceiveBuffer


@dataclass
class _Session:
    generation: int
    settings: DoIPSettings
    stop: threading.Event = field(default_factory=threading.Event)
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    sock: socket.socket | None = None
    connected: bool = False
    threads: list[threading.Thread] = field(default_factory=list)


class DoIPProtocol(QObject):
    connection_changed = Signal(int, bool, float)
    frame_received = Signal(int, bytes, float)
    incomplete_received = Signal(int, bytes, float)
    sending = Signal(int, bytes, float)
    error_occurred = Signal(int, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._life = threading.Lock()
        self._session: _Session | None = None
        self._generation = 0
        self._closed = False

    @property
    def generation(self):
        with self._life:
            return self._generation

    def is_connected(self):
        with self._life:
            return self._session is not None and self._session.connected and not self._session.stop.is_set()

    def is_quiescent(self):
        with self._life:
            return self._quiescent_locked()

    def _quiescent_locked(self):
        session = self._session
        return session is None or (
            not session.connected
            and (session.sock is None or session.sock.fileno() == -1)
            and all(not thread.is_alive() for thread in session.threads))

    def _spawn_locked(self, session, name, action, *, allow_stopped=False):
        if self._session is not session or (not allow_stopped and (self._closed or session.stop.is_set())):
            return False
        thread = threading.Thread(target=action, name=name, daemon=True)
        session.threads.append(thread)
        thread.start()
        return True

    def _spawn(self, session, name, action):
        with self._life:
            return self._spawn_locked(session, name, action)

    def connect_to(self, settings: DoIPSettings) -> int:
        with self._life:
            if self._closed or not self._quiescent_locked():
                raise RuntimeError("Diagnostic connection is closed or still releasing")
            self._generation += 1
            session = _Session(self._generation, settings)
            self._session = session
        self._spawn(session, "doip-connect", lambda: self._connect_worker(session))
        return session.generation

    def _connect_worker(self, session):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with self._life:
                session.sock = sock
            if session.stop.is_set():
                return
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
            sock.settimeout(session.settings.connect_timeout_ms / 1000)
            sock.connect((session.settings.target_ip, session.settings.target_port))
            sock.settimeout(0.2)
            with self._life:
                active = self._session is session and not session.stop.is_set()
                session.connected = active
            if not active:
                return
            self.connection_changed.emit(session.generation, True, time.time())
            self._spawn(session, "doip-receive", lambda: self._receive_worker(session))
        except Exception as exc:
            if not session.stop.is_set():
                self.error_occurred.emit(session.generation, f"TCP 连接失败: {exc}", time.time())
                self._end(session)
        finally:
            if session.stop.is_set() or not session.connected:
                self._close_socket(sock)

    @staticmethod
    def _close_socket(sock):
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def _end(self, session):
        with self._life:
            first = not session.stop.is_set()
            session.stop.set()
            session.connected = False
            sock = session.sock
        self._close_socket(sock)
        if first:
            self.connection_changed.emit(session.generation, False, time.time())

    def _receive_worker(self, session):
        buffer = DoIPReceiveBuffer(session.settings.max_payload_length)
        try:
            while not session.stop.is_set():
                try:
                    chunk = session.sock.recv(262144)
                except socket.timeout:
                    continue
                if not chunk:
                    if buffer.pending_bytes:
                        pending = buffer.pending_bytes
                        stamp = time.time()
                        self.incomplete_received.emit(session.generation, pending, stamp)
                        self.error_occurred.emit(session.generation,
                            f"远端关闭，未完成 DoIP 帧 {len(pending)}B，完整字节见不完整帧日志", stamp)
                    else:
                        self.error_occurred.emit(session.generation, "远端关闭诊断 TCP", time.time())
                    break
                buffer.feed(chunk)
                while not session.stop.is_set():
                    raw = buffer.try_extract()
                    for error in buffer.take_errors():
                        self.error_occurred.emit(session.generation, error, time.time())
                    if raw is None:
                        break
                    self.frame_received.emit(session.generation, raw, time.time())
                    frame = decode_frame(raw)
                    if frame.version == session.settings.protocol_version and frame.payload_type == PayloadType.ALIVE_REQUEST and not frame.payload:
                        self.send(build_frame(PayloadType.ALIVE_RESPONSE,
                            session.settings.source_address.to_bytes(2, "big"), session.settings.protocol_version), generation=session.generation)
        except Exception as exc:
            if not session.stop.is_set():
                self.error_occurred.emit(session.generation, f"TCP 接收失败: {exc}", time.time())
        finally:
            self._end(session)

    def send(self, data: bytes, *, generation: int) -> bool:
        with self._life:
            session = self._session
            accepted = (not self._closed and session is not None and generation == session.generation
                        and session.connected and not session.stop.is_set())
        if not accepted:
            return False
        return self._spawn(session, "doip-send", lambda: self._send_worker(session, data))

    def _send_worker(self, session, data):
        with session.send_lock:
            if session.stop.is_set():
                return
            try:
                self.sending.emit(session.generation, data, time.time())
                session.sock.sendall(data)
            except Exception as exc:
                if not session.stop.is_set():
                    self.error_occurred.emit(session.generation, f"TCP 写出失败: {exc}", time.time())
                self._end(session)

    def disconnect(self):
        with self._life:
            session = self._session
            if session is None or session.stop.is_set():
                return
            session.stop.set()
            session.connected = False
            # Stop and close-worker registration are atomic; IO stays in the worker.
            self._spawn_locked(session, "doip-close", lambda: self._close_socket(session.sock), allow_stopped=True)
        self.connection_changed.emit(session.generation, False, time.time())

    def poll(self):
        with self._life:
            if self._session is not None:
                self._session.threads[:] = [thread for thread in self._session.threads if thread.is_alive()]

    def shutdown(self):
        with self._life:
            self._closed = True
        self.disconnect()
        # Called after the GUI loop; one total deadline, no lock held during joins.
        deadline = time.monotonic() + 2
        while True:
            with self._life:
                if self._quiescent_locked():
                    return
                threads = tuple(thread for thread in self._session.threads if thread.is_alive())
            if not threads or time.monotonic() >= deadline:
                raise RuntimeError("Diagnostic TCP workers did not stop")
            for thread in threads:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                thread.join(timeout=remaining)
