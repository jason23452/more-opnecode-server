from __future__ import annotations

import select
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
        if not msvcrt.kbhit():
            return b""
        character = msvcrt.getwch()
        if character in ("\x00", "\xe0") and msvcrt.kbhit():
            return {"H": b"\x1b[A", "P": b"\x1b[B", "M": b"\x1b[C", "K": b"\x1b[D"}.get(
                msvcrt.getwch(), b""
            )
        return character.encode("utf-8", errors="replace")
    readable, _, _ = select.select([sys.stdin], [], [], 0.05)
    return sys.stdin.buffer.read1(4096) if readable else b""


def connect_terminal(url: str, token: str) -> None:
    old_settings = None
    if termios and sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
    try:
        with websocket_connect(
            url, additional_headers={"Authorization": f"Bearer {token}"},
            max_size=None, ping_interval=20,
        ) as remote:
            while True:
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
