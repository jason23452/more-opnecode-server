"""Container-local authenticated WebSocket to a PTY-backed OpenCode TUI."""

from __future__ import annotations

import hmac
import json
import os
import re
import select
import subprocess
import threading
import uuid
from pathlib import Path

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

PROJECT = Path("/workspace/project")
CLIPBOARD_FILE_PREFIX = b"\x00OPENCODE_CLIPBOARD_FILE_V1\x00"
MAX_CLIPBOARD_FILE_BYTES = 25 * 1024 * 1024

_SESSION_LOCK = threading.Lock()
_SESSION_ACTIVE = False


def _reject(connection: ServerConnection, code: int, reason: str) -> None:
    connection.close(code=code, reason=reason)


def _handle_clipboard_file(message: bytes, stdin) -> bool:
    """Store an authorized clipboard file and paste its workspace reference."""
    if not message.startswith(CLIPBOARD_FILE_PREFIX):
        return False
    metadata_bytes, separator, content = message[len(CLIPBOARD_FILE_PREFIX):].partition(b"\x00")
    if not separator or len(metadata_bytes) > 4096 or len(content) > MAX_CLIPBOARD_FILE_BYTES:
        return True
    try:
        metadata = json.loads(metadata_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return True
    original_name = metadata.get("name") if isinstance(metadata, dict) else None
    mime_type = metadata.get("mime_type") if isinstance(metadata, dict) else None
    if (not isinstance(original_name, str) or not original_name or len(original_name) > 255
            or Path(original_name).name != original_name or "/" in original_name or "\\" in original_name
            or any(ord(character) < 32 for character in original_name)
            or not isinstance(mime_type, str) or len(mime_type) > 255):
        return True

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._")[:120] or "file"
    name = f"clipboard-{uuid.uuid4().hex}-{safe_name}"
    PROJECT.mkdir(parents=True, exist_ok=True)
    destination = PROJECT / name
    temporary = PROJECT / f".{name}.tmp"
    temporary.write_bytes(content)
    os.replace(temporary, destination)
    relative_path = destination.relative_to(PROJECT).as_posix()
    stdin.write(b"\x1b[200~ @" + relative_path.encode("utf-8") + b"\x1b[201~")
    stdin.flush()
    return True


def relay(connection: ServerConnection) -> None:
    global _SESSION_ACTIVE
    expected = os.environ.get("OPENCODE_CONNECT_TOKEN", "")
    supplied = connection.request.headers.get("Authorization", "")
    if not expected or not hmac.compare_digest(supplied, "Bearer " + expected):
        _reject(connection, 4401, "Invalid connect token")
        return
    with _SESSION_LOCK:
        if _SESSION_ACTIVE:
            _reject(connection, 4409, "TUI session already active")
            return
        _SESSION_ACTIVE = True

    process = None
    resize_write = None
    try:
        os.makedirs("/workspace/project", exist_ok=True)
        resize_read, resize_write = os.pipe()
        process = subprocess.Popen(
            ["python3", "/usr/local/bin/opencode-pty-runner", "sh", "-lc",
             "cd /workspace/project && exec opencode ."],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            pass_fds=(resize_read,),
            env={**os.environ, "OPENCODE_PTY_RESIZE_FD": str(resize_read)},
        )
        os.close(resize_read)
        while process.poll() is None:
            readable, _, _ = select.select([process.stdout], [], [], 0.02)
            if readable:
                output = os.read(process.stdout.fileno(), 65536)
                if output:
                    connection.send(output)
            try:
                incoming = connection.recv(timeout=0.02)
            except TimeoutError:
                continue
            if isinstance(incoming, bytes) and incoming:
                if not _handle_clipboard_file(incoming, process.stdin):
                    process.stdin.write(incoming)
                    process.stdin.flush()
            elif isinstance(incoming, str):
                try:
                    control = json.loads(incoming)
                    columns, rows = control["columns"], control["rows"]
                    if (control.get("type") == "resize"
                            and type(columns) is int and type(rows) is int
                            and 1 <= columns <= 1000 and 1 <= rows <= 1000):
                        os.write(resize_write, json.dumps(
                            {"columns": columns, "rows": rows}, separators=(",", ":")
                        ).encode() + b"\n")
                except (ValueError, KeyError, TypeError, OSError):
                    pass
    except ConnectionClosed:
        pass
    finally:
        if resize_write is not None:
            os.close(resize_write)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        with _SESSION_LOCK:
            _SESSION_ACTIVE = False


def main() -> None:
    server = serve(relay, "127.0.0.1", 4098, max_size=None, ping_interval=20)
    server.serve_forever()


if __name__ == "__main__":
    main()
