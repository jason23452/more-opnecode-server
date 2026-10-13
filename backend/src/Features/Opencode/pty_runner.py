"""Run a command attached to a real container-local controlling PTY."""

import fcntl
import os
import pty
import select
import signal
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
    old = termios.tcgetattr(sys.stdin.fileno()) if sys.stdin.isatty() else None
    if old:
        tty.setraw(sys.stdin.fileno())
    disconnected_at = None
    try:
        while True:
            ready, _, _ = select.select([master, sys.stdin.fileno()], [], [], 0.1)
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
