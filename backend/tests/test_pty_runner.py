import subprocess
import sys
import os
import select
import fcntl
import json
import pty
import struct
import termios
import time
from pathlib import Path


def test_pty_runner_gives_child_a_controlling_tty_and_relays_input() -> None:
    runner = Path(__file__).parents[1] / "src/Features/Opencode/pty_runner.py"
    child = "import os,sys; print('TTY='+str(os.isatty(0)), flush=True); print('KEY='+sys.stdin.read(1), flush=True)"

    process = subprocess.Popen(
        [sys.executable, str(runner), sys.executable, "-c", child],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    process.stdin.write(b"k")
    process.stdin.flush()
    assert process.stdout is not None
    stdout = bytearray()
    while process.poll() is None:
        ready, _, _ = select.select([process.stdout], [], [], 1)
        if ready:
            stdout.extend(os.read(process.stdout.fileno(), 4096))
    stdout.extend(process.stdout.read())
    stderr = process.stderr.read() if process.stderr else b""

    assert process.returncode == 0, stderr
    assert b"TTY=True" in stdout
    assert b"KEY=k" in stdout


def test_pty_runner_applies_initial_and_changed_window_size_to_child() -> None:
    runner = Path(__file__).parents[1] / "src/Features/Opencode/pty_runner.py"
    read_fd, write_fd = os.pipe()
    child = (
        "import fcntl,os,struct,sys,termios; "
        "print('TTY='+str(os.isatty(0)),flush=True); "
        "exec('while True:\\n sys.stdin.buffer.read(1)\\n "
        "h,w,_,_=struct.unpack(\"HHHH\",fcntl.ioctl(0,termios.TIOCGWINSZ,b\"\\\\0\"*8))\\n "
        "print(f\"SIZE={w}x{h}\",flush=True)')"
    )
    process = subprocess.Popen(
        [sys.executable, str(runner), sys.executable, "-c", child],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        pass_fds=(read_fd,), env={**os.environ, "OPENCODE_PTY_RESIZE_FD": str(read_fd)},
    )
    os.close(read_fd)
    assert process.stdin and process.stdout
    stdout = bytearray()

    def resize(columns: int, rows: int) -> None:
        os.write(write_fd, (json.dumps({"columns": columns, "rows": rows}) + "\n").encode())
        process.stdin.write(b"x")
        process.stdin.flush()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and f"SIZE={columns}x{rows}".encode() not in stdout:
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if ready:
                stdout.extend(os.read(process.stdout.fileno(), 4096))

    try:
        resize(100, 30)
        resize(132, 44)
    finally:
        os.close(write_fd)
        process.terminate()
        process.wait(timeout=3)
    assert b"SIZE=100x30" in stdout
    assert b"SIZE=132x44" in stdout
