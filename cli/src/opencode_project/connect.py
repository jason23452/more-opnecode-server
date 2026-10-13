from __future__ import annotations

import json
import os
import re
import select
import shutil
import sys

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

_TERMINAL_QUERY_REPLIES = re.compile(
    rb"\x1b\[\?[0-9;]+\$y|"       # DEC private-mode report
    rb"\x1b\[[0-9]+;[0-9]+R|"      # cursor-position report
    rb"\x1b\[4;[0-9]+;[0-9]+t|"   # text-area size report
    rb"\x1b\[[?>][0-9;]+c|"        # device-attributes report
    rb"\x1b\]10;rgb:[0-9a-fA-F/]+(?:\x07|\x1b\\)"  # foreground-color report
)


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
    if msvcrt and sys.stdin.isatty():
        data = bytearray()
        special_keys = {"H": b"\x1b[A", "P": b"\x1b[B", "M": b"\x1b[C", "K": b"\x1b[D"}
        while msvcrt.kbhit():
            character = msvcrt.getwch()
            if character in ("\x00", "\xe0"):
                if msvcrt.kbhit():
                    data.extend(special_keys.get(msvcrt.getwch(), b""))
                continue
            data.extend(character.encode("utf-8", errors="replace"))
        # Windows Terminal sends responses to TUI capability queries through
        # the same console input stream as keystrokes. Do not relay those
        # responses back to the remote TUI as if the user had typed them.
        return _TERMINAL_QUERY_REPLIES.sub(b"", bytes(data))
    readable, _, _ = select.select([sys.stdin], [], [], 0.05)
    return sys.stdin.buffer.read1(4096) if readable else b""


def terminal_size() -> tuple[int, int]:
    """Return terminal columns and rows on Windows and POSIX terminals."""
    try:
        size = os.get_terminal_size(sys.stdin.fileno())
    except (AttributeError, OSError, ValueError):
        size = shutil.get_terminal_size()
    return max(1, size.columns), max(1, size.lines)


def connect_terminal(url: str, token: str) -> None:
    old_settings = None
    if termios and sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
    try:
        with websocket_connect(
            url, additional_headers={"Authorization": f"Bearer {token}"},
            max_size=None, ping_interval=20, close_timeout=2,
        ) as remote:
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
                    remote.send(data)
                    if b"\x03" in data:
                        return
                try:
                    output = remote.recv(timeout=0.05)
                except TimeoutError:
                    continue
                if isinstance(output, bytes):
                    sys.stdout.buffer.write(output)
                    sys.stdout.buffer.flush()
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
        message = _known_close_message_from_error(error) or (
            "Tunnel 網路連線失敗。請透過管理 API 重新查詢目前的 connect_url，"
            "並使用原容器 connect token 重新執行 connect。"
        )
        raise RuntimeError(f"遠端 TUI 連線失敗：{message}") from error
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
