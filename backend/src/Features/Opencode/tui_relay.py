"""Container-local authenticated WebSocket to a PTY-backed OpenCode TUI."""

from __future__ import annotations

import hmac
import json
import os
import select
import subprocess
import threading

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

_SESSION_LOCK = threading.Lock()
_SESSION_ACTIVE = False


def _reject(connection: ServerConnection, code: int, reason: str) -> None:
    connection.close(code=code, reason=reason)


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
