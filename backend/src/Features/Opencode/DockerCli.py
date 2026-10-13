from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def docker_executable() -> str:
    if is_wsl() and shutil.which("docker.exe"):
        return shutil.which("docker.exe") or "docker.exe"
    return shutil.which("docker") or "docker"


def docker_path(path: str) -> str:
    if not (is_wsl() and Path(path).is_absolute()):
        return path
    converter = shutil.which("wslpath")
    if converter:
        result = subprocess.run([converter, "-w", path], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    return path


def docker_command(*args: str) -> list[str]:
    executable = docker_executable()
    converted = list(args)
    if "build" in converted:
        # Docker Desktop resolves the build context on Windows, not inside WSL.
        for index, value in enumerate(converted):
            if value.startswith("/"):
                converted[index] = docker_path(value)
    return [executable, *converted]
