from __future__ import annotations

import json
import os
import re
import select
import ssl
import shutil
import struct
import sys
import threading
from urllib.parse import urlsplit, urlunsplit

try:
    import termios
    import tty
except ImportError:  # pragma: no cover - exercised on Windows
    termios = None
    tty = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX
    msvcrt = None

from websockets.sync.client import connect as websocket_connect
from websockets.exceptions import ConnectionClosed

from .clipboard import read_clipboard_files
from .agent_socket import connect_agent, ssh_agent_address
from .tls import create_ssl_context

_CLIPBOARD_FILE_PREFIX = b"\x00OPENCODE_CLIPBOARD_FILE_V1\x00"
_CLIPBOARD_PASTE_TRIGGERS = {b"\x16", b"\x07"}  # Ctrl+V, Ctrl+G fallback
_TERMINAL_QUERY_REPLIES = re.compile(
    rb"\x1b\[\?[0-9;]+\$y|"       # DEC private-mode report
    rb"\x1b\[[0-9]+;[0-9]+R|"      # cursor-position report
    rb"\x1b\[4;[0-9]+;[0-9]+t|"   # text-area size report
    rb"\x1b\[[?>][0-9;]+c|"        # device-attributes report
    rb"\x1b\]10;rgb:[0-9a-fA-F/]+(?:\x07|\x1b\\)"  # foreground-color report
)
_PENDING_WINDOWS_KEY_PREFIX = False
_MAX_AGENT_PACKET = 256 * 1024
_AGENT_RELAY_READY = "opencode-ssh-agent-ready-v1"


def _valid_agent_packet(packet: bytes) -> bool:
    return (5 <= len(packet) <= _MAX_AGENT_PACKET + 4
            and struct.unpack(">I", packet[:4])[0] == len(packet) - 4)


def _allowed_agent_request(packet: bytes) -> bool:
    if not _valid_agent_packet(packet):
        return False
    if packet[4] in {11, 13}:  # Request identities / sign request.
        return True
    if packet[4] != 27:  # SSH_AGENTC_EXTENSION
        return False
    payload = packet[5:]
    if len(payload) < 4:
        return False
    extension_size = struct.unpack(">I", payload[:4])[0]
    return payload[4:4 + extension_size] == b"session-bind@openssh.com"


def _allowed_agent_response(request: bytes, response: bytes) -> bool:
    if not _valid_agent_packet(response):
        return False
    expected = {11: 12, 13: 14, 27: 6}.get(request[4])
    return response[4] == 5 or response[4] == expected


def _read_agent_packet(agent) -> bytes:
    header = bytearray()
    while len(header) < 4:
        chunk = agent.recv(4 - len(header))
        if not chunk:
            raise ConnectionError("本機 SSH agent 已中斷")
        header.extend(chunk)
    size = struct.unpack(">I", header)[0]
    if not 1 <= size <= _MAX_AGENT_PACKET:
        raise ValueError("本機 SSH agent 回覆超過允許大小")
    payload = bytearray()
    while len(payload) < size:
        chunk = agent.recv(size - len(payload))
        if not chunk:
            raise ConnectionError("本機 SSH agent 回覆不完整")
        payload.extend(chunk)
    return bytes(header + payload)


def _agent_tunnel_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/ssh-agent", "", ""))


def _forward_agent_requests(url: str, token: str, stop: threading.Event) -> None:
    socket_path = ssh_agent_address()
    if not socket_path:
        return
    options = {
        "additional_headers": {"Authorization": f"Bearer {token}"},
        "max_size": _MAX_AGENT_PACKET + 4,
        "ping_interval": 20,
        "close_timeout": 1,
    }
    if urlsplit(url).scheme == "wss":
        options["ssl"] = create_ssl_context()
    failures = 0
    while not stop.is_set():
        try:
            with websocket_connect(_agent_tunnel_url(url), **options) as relay:
                if relay.recv(timeout=5) != _AGENT_RELAY_READY:
                    raise RuntimeError("容器 SSH agent relay 未就緒")
                with connect_agent(socket_path) as agent:
                    if hasattr(agent, "settimeout"):
                        agent.settimeout(10)
                    while not stop.is_set():
                        try:
                            packet = relay.recv(timeout=0.1)
                        except TimeoutError:
                            continue
                        if not isinstance(packet, bytes) or not _allowed_agent_request(packet):
                            raise RuntimeError("容器傳回無效 SSH agent 封包")
                        agent.sendall(packet)
                        response = _read_agent_packet(agent)
                        if not _allowed_agent_response(packet, response):
                            raise RuntimeError("本機 SSH agent 傳回不符合協定的回應")
                        relay.send(response)
        except (OSError, RuntimeError, TimeoutError, ssl.SSLError, ConnectionClosed) as error:
            if stop.wait(0.25):
                return
            # The TUI handshake may complete just before the server marks the
            # session active; retry until its authenticated relay is ready.
            if isinstance(error, ConnectionClosed) and error.rcvd and error.rcvd.code == 4401:
                print(f"SSH agent 即時轉送未啟用：{error}", file=sys.stderr)
                return
            failures += 1
            if failures == 5:
                print(f"SSH agent 即時轉送尚未就緒，將持續重試：{error}", file=sys.stderr)
        except Exception as error:
            print(f"SSH agent relay failed: {type(error).__name__}: {error}", file=sys.stderr)
            return


def _known_close_message(code: int | None) -> str | None:
    return {
        4401: "連線授權無效或已撤銷，請使用最新的容器連線資訊。",
        4404: "找不到此 OpenCode 容器。",
        4409: "此容器已有 TUI 工作階段，請稍後重試。",
    }.get(code)


def _known_close_message_from_error(error: Exception) -> str | None:
    message = str(error)
    for code in (4401, 4409, 4404):
        if str(code) in message:
            return _known_close_message(code)
    return None


def _terminal_input() -> bytes:
    global _PENDING_WINDOWS_KEY_PREFIX
    if msvcrt and sys.stdin.isatty():
        data = bytearray()
        special_keys = {
            "H": b"\x1b[A", "P": b"\x1b[B", "M": b"\x1b[C", "K": b"\x1b[D",
            "C": b"\x07",  # F9 clipboard-paste fallback
        }
        if _PENDING_WINDOWS_KEY_PREFIX:
            if not msvcrt.kbhit():
                return b""
            data.extend(special_keys.get(msvcrt.getwch(), b""))
            _PENDING_WINDOWS_KEY_PREFIX = False
        while msvcrt.kbhit():
            character = msvcrt.getwch()
            if character in ("\x00", "\xe0"):
                if msvcrt.kbhit():
                    data.extend(special_keys.get(msvcrt.getwch(), b""))
                    continue
                # Windows may make the extended-key prefix available before
                # its scan code. Keep the prefix for the next poll instead
                # of leaking H/P/M/K to the remote TUI as ordinary text.
                _PENDING_WINDOWS_KEY_PREFIX = True
                break
            data.extend(character.encode("utf-8", errors="replace"))
        # Windows Terminal sends responses to TUI capability queries through
        # the same console input stream as keystrokes. Do not relay those
        # responses back to the remote TUI as if the user had typed them.
        return _TERMINAL_QUERY_REPLIES.sub(b"", bytes(data))
    readable, _, _ = select.select([sys.stdin], [], [], 0.05)
    if not readable:
        return b""
    return sys.stdin.buffer.read1(4096).replace(b"\x1b[20~", b"\x07")


def terminal_size() -> tuple[int, int]:
    """Return terminal columns and rows on Windows and POSIX terminals."""
    try:
        size = os.get_terminal_size(sys.stdin.fileno())
    except (AttributeError, OSError, ValueError):
        size = shutil.get_terminal_size()
    return max(1, size.columns), max(1, size.lines)


def _send_terminal_input(remote, data: bytes) -> None:
    pending = bytearray()
    for value in data:
        character = bytes((value,))
        if character not in _CLIPBOARD_PASTE_TRIGGERS:
            pending.extend(character)
            continue
        if pending:
            remote.send(bytes(pending))
            pending.clear()
        files = read_clipboard_files()
        if files:
            for item in files:
                metadata = json.dumps(
                    {"name": item.name, "mime_type": item.mime_type},
                    ensure_ascii=False, separators=(",", ":"),
                ).encode("utf-8")
                remote.send(_CLIPBOARD_FILE_PREFIX + metadata + b"\x00" + item.data)
        else:
            remote.send(character)
    if pending:
        remote.send(bytes(pending))


def connect_terminal(url: str, token: str, forward_ssh_agent: bool = False) -> None:
    global _PENDING_WINDOWS_KEY_PREFIX
    _PENDING_WINDOWS_KEY_PREFIX = False
    old_settings = None
    if termios and sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
    try:
        connection_options = {
            "additional_headers": {"Authorization": f"Bearer {token}"},
            "max_size": None,
            "ping_interval": 20,
            "close_timeout": 2,
        }
        if urlsplit(url).scheme == "wss":
            connection_options["ssl"] = create_ssl_context()
        with websocket_connect(url, **connection_options) as remote:
            agent_stop = threading.Event()
            agent_thread = None
            if forward_ssh_agent and ssh_agent_address():
                agent_thread = threading.Thread(
                    target=_forward_agent_requests, args=(url, token, agent_stop), daemon=True,
                )
                agent_thread.start()
            try:
                last_size = None
                while True:
                    size = terminal_size()
                    if size != last_size:
                        columns, rows = size
                        remote.send(json.dumps(
                            {"type": "resize", "columns": columns, "rows": rows},
                            separators=(",", ":"),
                        ))
                        last_size = size
                    data = _terminal_input()
                    if data:
                        _send_terminal_input(remote, data)
                        if b"\x03" in data:
                            return
                    try:
                        output = remote.recv(timeout=0.05)
                    except TimeoutError:
                        continue
                    if isinstance(output, bytes):
                        sys.stdout.buffer.write(output)
                        sys.stdout.buffer.flush()
            finally:
                agent_stop.set()
                if agent_thread is not None:
                    agent_thread.join(timeout=1)
    except KeyboardInterrupt:
        print("\n遠端 TUI 連線已中斷。可再次執行 connect 重新連線。", file=sys.stderr)
    except ConnectionClosed as error:
        known_message = _known_close_message(error.rcvd.code if error.rcvd else None)
        if known_message:
            raise RuntimeError(known_message) from error
        raise RuntimeError(
            "遠端 TUI Tunnel 連線中斷。請透過管理 API 重新查詢目前的 connect_url，"
            "並使用原容器 connect token 重新執行 connect。"
        ) from error
    except Exception as error:
        message = _known_close_message_from_error(error)
        if message is None and isinstance(error, ssl.SSLCertVerificationError):
            message = (
                f"Tunnel TLS 憑證驗證失敗：{error}。CLI 使用內建公開 CA 憑證；"
                "若網路使用自訂或公司 TLS 憑證，請將 SSL_CERT_FILE 設為受信任的 CA 憑證檔後重試。"
            )
        message = message or (
            "Tunnel 網路連線失敗。請透過管理 API 重新查詢目前的 connect_url，"
            "並使用原容器 connect token 重新執行 connect。"
        )
        raise RuntimeError(f"遠端 TUI 連線失敗：{message}") from error
    finally:
        _PENDING_WINDOWS_KEY_PREFIX = False
        if old_settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
