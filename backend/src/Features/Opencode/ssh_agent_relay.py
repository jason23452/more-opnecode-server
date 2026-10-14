"""Authenticated, bounded SSH-agent WebSocket relay for an active TUI session."""

from __future__ import annotations

import hmac
import logging
import os
import socket
import stat
import struct
import threading
from pathlib import Path

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

MAX_AGENT_PACKET = 256 * 1024
RELAY_READY = "opencode-ssh-agent-ready-v1"
DEFAULT_AGENT_SOCKET = "/run/opencode/ssh-agent.sock"
TUI_ACTIVE_MARKER = "/run/opencode/tui-active"
_AGENT_SESSION_LOCK = threading.Lock()
_LOGGER = logging.getLogger(__name__)


def read_agent_packet(stream, buffer: bytearray | None = None) -> bytes | None:
    """Read a complete SSH-agent packet without accepting unbounded lengths."""
    pending = buffer if buffer is not None else bytearray()
    while len(pending) < 4:
        try:
            block = stream.recv(64 * 1024)
        except (OSError, TimeoutError):
            return None
        if not block:
            raise ConnectionError("SSH agent client disconnected")
        pending.extend(block)
    size = struct.unpack(">I", pending[:4])[0]
    if not 1 <= size <= MAX_AGENT_PACKET:
        pending.clear()
        raise ValueError("SSH agent packet exceeds the configured limit")
    total_size = size + 4
    while len(pending) < total_size:
        try:
            block = stream.recv(min(64 * 1024, total_size - len(pending)))
        except (OSError, TimeoutError):
            return None
        if not block:
            raise ConnectionError("SSH agent client disconnected")
        pending.extend(block)
    packet = bytes(pending[:total_size])
    del pending[:total_size]
    return packet


def _valid_packet(packet: bytes) -> bool:
    return len(packet) >= 5 and len(packet) <= MAX_AGENT_PACKET + 4 and struct.unpack(">I", packet[:4])[0] == len(packet) - 4


def agent_request_allowed(packet: bytes) -> bool:
    if not _valid_packet(packet):
        return False
    request_type = packet[4]
    if request_type in {11, 13}:  # Request identities / sign request.
        return True
    if request_type != 27:  # SSH_AGENTC_EXTENSION
        return False
    payload = packet[5:]
    if len(payload) < 4:
        return False
    extension_size = struct.unpack(">I", payload[:4])[0]
    return payload[4:4 + extension_size] == b"session-bind@openssh.com"


def agent_response_allowed(request: bytes, response: bytes) -> bool:
    if not _valid_packet(response):
        return False
    expected = {11: 12, 13: 14, 27: 6}.get(request[4])
    return response[4] == 5 or response[4] == expected


def relay(connection: ServerConnection) -> None:
    expected = os.environ.get("OPENCODE_CONNECT_TOKEN", "")
    supplied = connection.request.headers.get("Authorization", "")
    if not expected or not hmac.compare_digest(supplied, "Bearer " + expected):
        connection.close(code=4401, reason="Invalid connect token")
        return
    marker = Path(os.environ.get("OPENCODE_TUI_ACTIVE_MARKER", TUI_ACTIVE_MARKER))
    if not marker.exists():
        connection.close(code=4409, reason="TUI session is not active")
        return
    if not _AGENT_SESSION_LOCK.acquire(blocking=False):
        connection.close(code=4409, reason="SSH agent relay already active")
        return

    socket_path = Path(os.environ.get("OPENCODE_SSH_AGENT_SOCKET", DEFAULT_AGENT_SOCKET))
    listener = None
    try:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.unlink(missing_ok=True)
        listener.bind(str(socket_path))
        os.chmod(socket_path, stat.S_IRUSR | stat.S_IWUSR)
        listener.listen(1)
        listener.settimeout(0.2)
        connection.send(RELAY_READY)
        _LOGGER.debug("SSH agent relay ready on %s", socket_path)
        while marker.exists():
            try:
                client, _ = listener.accept()
            except TimeoutError:
                try:
                    incoming = connection.recv(timeout=0.02)
                except TimeoutError:
                    continue
                if incoming is None:
                    return
                connection.close(code=4400, reason="Unexpected SSH agent response")
                return
            _LOGGER.debug("SSH agent client connected")
            with client:
                client.settimeout(0.2)
                pending = bytearray()
                while marker.exists():
                    try:
                        packet = read_agent_packet(client, pending)
                    except ValueError:
                        connection.close(code=4400, reason="Invalid SSH agent packet")
                        return
                    except ConnectionError:
                        break
                    if packet is None:
                        # SSH agent clients may be idle between requests. Poll
                        # the authenticated WebSocket to observe disconnects.
                        try:
                            incoming = connection.recv(timeout=0.02)
                        except TimeoutError:
                            continue
                        if incoming is None:
                            return
                        connection.close(code=4400, reason="Unexpected SSH agent response")
                        return
                    if not agent_request_allowed(packet):
                        connection.close(code=4400, reason="SSH agent request type is not allowed")
                        return
                    _LOGGER.debug("SSH agent request received (%d bytes)", len(packet))
                    connection.send(packet)
                    try:
                        response = connection.recv(timeout=10)
                    except TimeoutError:
                        connection.close(code=4408, reason="SSH agent response timed out")
                        return
                    if not isinstance(response, bytes) or not agent_response_allowed(packet, response):
                        connection.close(code=4400, reason="Invalid agent response")
                        return
                    _LOGGER.debug("SSH agent response received (%d bytes)", len(response))
                    client.sendall(response)
    except (ConnectionClosed, OSError) as error:
        _LOGGER.info("SSH agent relay ended: %s", error)
        return
    except Exception:
        _LOGGER.exception("SSH agent relay failed")
        return
    finally:
        try:
            if listener is not None:
                listener.close()
            socket_path.unlink(missing_ok=True)
        finally:
            _AGENT_SESSION_LOCK.release()


def main() -> None:
    server = serve(relay, "127.0.0.1", 4099, max_size=MAX_AGENT_PACKET + 4, ping_interval=20)
    server.serve_forever()


if __name__ == "__main__":
    main()
