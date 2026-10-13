"""Container-local authenticated WebSocket to a PTY-backed OpenCode TUI."""

from __future__ import annotations

import hmac
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
    try:
        process = subprocess.Popen(
            ["python3", "/usr/local/bin/opencode-pty-runner", "sh", "-lc",
             "cd /workspace/project && exec opencode ."],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
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
                process.stdin.write(incoming.encode())
                process.stdin.flush()
    except ConnectionClosed:
        pass
    finally:
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
