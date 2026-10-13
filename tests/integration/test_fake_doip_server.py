"""Loopback checks for the explicit queued-response fixture and its cleanup."""

import socket
import struct

import pytest

from tests.fixtures.fake_doip_server import FakeDoIPServer


def make_frame(payload: bytes, payload_type: int = 0x8001) -> bytes:
    return struct.pack("!BBHI", 2, 0xFD, payload_type, len(payload)) + payload


def receive_exact(client: socket.socket, count: int) -> bytes:
    received = bytearray()
    while len(received) < count:
        chunk = client.recv(count - len(received))
        assert chunk, "connection closed before the queued response was received"
        received.extend(chunk)
    return bytes(received)


@pytest.mark.parametrize("split_at", [1, 7, 8, 10])
def test_fragmented_header_and_payload_wait_for_complete_frame(split_at):
    request = make_frame(b"\x0e\x80\x10\x01\x22\xf1\x90")
    response = make_frame(b"\x10\x01\x0e\x80\x62\xf1\x90\x00")
    with FakeDoIPServer() as server:
        server.queue_response(response)
        with socket.create_connection(server.address, timeout=1.0) as client:
            client.sendall(request[:split_at])
            assert not server.wait_for_received(1, timeout=0.03)
            client.sendall(request[split_at:])
            assert receive_exact(client, len(response)) == response
            assert server.wait_for_received(1)
            assert server.received == (request,)
    assert server.closed
    assert server.error is None


def test_coalesced_frames_consume_queued_responses_in_order():
    requests = (make_frame(b"first"), make_frame(b"second"))
    responses = (make_frame(b"reply-one"), make_frame(b"reply-two"))
    with FakeDoIPServer() as server:
        for response in responses:
            server.queue_response(response)
        with socket.create_connection(server.address, timeout=1.0) as client:
            client.sendall(b"".join(requests))
            assert receive_exact(client, sum(map(len, responses))) == b"".join(responses)
            assert server.wait_for_received(2)
            assert server.received == requests
    assert server.error is None


def test_request_without_prequeued_response_does_not_get_implicit_success():
    first = make_frame(b"\x27\x01")
    second = make_frame(b"\x27\x02")
    explicit_response = make_frame(b"explicit fixture bytes")
    with FakeDoIPServer() as server:
        with socket.create_connection(server.address, timeout=1.0) as client:
            client.sendall(first)
            assert server.wait_for_received(1)
            client.settimeout(0.05)
            with pytest.raises(socket.timeout):
                client.recv(1)
            server.queue_response(explicit_response)
            client.settimeout(1.0)
            client.sendall(second)
            assert receive_exact(client, len(explicit_response)) == explicit_response
            assert server.wait_for_received(2)
    assert server.error is None


def test_stop_while_waiting_for_client_releases_daemon_and_listener():
    server = FakeDoIPServer().start()
    worker = server.worker
    assert worker is not None and worker.daemon
    server.stop()
    server.stop()
    assert server.closed
    assert not worker.is_alive()
    assert server.error is None


def test_stop_while_receiving_releases_connected_socket_and_worker():
    server = FakeDoIPServer().start()
    with socket.create_connection(server.address, timeout=1.0) as client:
        assert server.wait_for_connection()
        client.sendall(make_frame(b"incomplete")[:5])
        server.stop()
        assert client.recv(1) == b""
    assert server.closed
    assert server.worker is not None and not server.worker.is_alive()
    assert server.error is None


def test_test_only_payload_limit_closes_oversized_request():
    with FakeDoIPServer(max_payload_length=3) as server:
        with socket.create_connection(server.address, timeout=1.0) as client:
            client.sendall(make_frame(b"four"))
            assert server.wait_for_stopped()
            assert client.recv(1) == b""
        assert server.received == ()
        assert isinstance(server.error, ValueError)
    assert server.closed


def test_context_manager_cleans_up_when_test_body_raises():
    with pytest.raises(ValueError, match="fixture body"):
        with FakeDoIPServer() as server:
            raise ValueError("fixture body")
    assert server.closed
    assert server.worker is not None and not server.worker.is_alive()
