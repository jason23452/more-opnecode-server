import subprocess
import sys
import os
import select
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
