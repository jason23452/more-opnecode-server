"""Run a command attached to a real container-local controlling PTY."""

import fcntl
import json
import os
import pty
import select
import signal
import struct
import sys
import termios
import time
import tty


def run(command: list[str]) -> int:
    master, slave = pty.openpty()
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        if slave > 2:
            os.close(slave)
        os.execvp(command[0], command)
    os.close(slave)
    tty.setraw(master)
    resize_fd = int(os.environ["OPENCODE_PTY_RESIZE_FD"]) if "OPENCODE_PTY_RESIZE_FD" in os.environ else None
    old = termios.tcgetattr(sys.stdin.fileno()) if sys.stdin.isatty() else None
    if old:
        tty.setraw(sys.stdin.fileno())
    disconnected_at = None
    try:
        while True:
            watched = [master, sys.stdin.fileno()]
            if resize_fd is not None:
                watched.append(resize_fd)
            ready, _, _ = select.select(watched, [], [], 0.1)
            if resize_fd in ready:
                control = os.read(resize_fd, 4096)
                for line in control.splitlines():
                    try:
                        size = json.loads(line)
                        columns, rows = size["columns"], size["rows"]
                        if (type(columns) is not int or type(rows) is not int
                                or not 1 <= columns <= 1000 or not 1 <= rows <= 1000):
                            continue
                    except (ValueError, KeyError, TypeError):
                        continue
                    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
                    try:
                        os.killpg(pid, signal.SIGWINCH)
                    except ProcessLookupError:
                        pass
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                if data:
                    os.write(sys.stdout.fileno(), data)
            if sys.stdin.fileno() in ready:
                data = os.read(sys.stdin.fileno(), 65536)
                if data:
                    os.write(master, data)
                else:
                    if disconnected_at is None:
                        disconnected_at = time.monotonic()
                        try:
                            os.killpg(pid, signal.SIGHUP)
                        except ProcessLookupError:
                            pass
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                return os.waitstatus_to_exitcode(status)
            if disconnected_at is not None:
                elapsed = time.monotonic() - disconnected_at
                if elapsed > 2:
                    try:
                        os.killpg(pid, signal.SIGTERM if elapsed < 3 else signal.SIGKILL)
                    except ProcessLookupError:
                        pass
    finally:
        if old:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        os.close(master)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
