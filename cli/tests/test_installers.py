from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


CLI_ROOT = Path(__file__).parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@pytest.mark.parametrize(
    ("system", "machine", "asset"),
    [
        ("Darwin", "arm64", "opencode-project-macos-arm64"),
        ("Darwin", "x86_64", "opencode-project-macos-x64"),
        ("Linux", "x86_64", "opencode-project-linux-x64"),
    ],
)
@pytest.mark.skipif(os.name == "nt", reason="POSIX installer is exercised on macOS and Linux runners")
def test_shell_installer_downloads_and_installs_matching_release_asset(
    tmp_path: Path, system: str, machine: str, asset: str,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "uname",
        '#!/bin/sh\ncase "$1" in -s) printf "%s\\n" "$TEST_SYSTEM" ;; '
        '-m) printf "%s\\n" "$TEST_MACHINE" ;; esac\n',
    )
    _write_executable(
        fake_bin / "curl",
        '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-fsSL" ]; then shift; url="$1"; fi\n'
        '  if [ "$1" = "-o" ]; then shift; output="$1"; fi\n'
        '  shift\ndone\nprintf "%s\\n" "$url" > "$ASSET_LOG"\nprintf "binary" > "$output"\n',
    )
    install_dir = tmp_path / "install"
    asset_log = tmp_path / "downloaded-url"
    env = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "OPENCODE_PROJECT_INSTALL_DIR": str(install_dir),
        "OPENCODE_PROJECT_RELEASE_URL": "https://releases.example/latest/download",
        "TEST_SYSTEM": system,
        "TEST_MACHINE": machine,
        "ASSET_LOG": str(asset_log),
    }

    result = subprocess.run(
        ["sh", str(CLI_ROOT / "install.sh")], env=env, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert asset_log.read_text(encoding="utf-8").strip() == (
        f"https://releases.example/latest/download/{asset}"
    )
    executable = install_dir / "opencode-project"
    assert executable.read_bytes() == b"binary"
    assert executable.stat().st_mode & 0o111


@pytest.mark.skipif(os.name == "nt", reason="POSIX installer is exercised on macOS and Linux runners")
def test_shell_installer_rejects_unsupported_architecture_without_downloading(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "uname",
        '#!/bin/sh\ncase "$1" in -s) printf "Linux\\n" ;; -m) printf "aarch64\\n" ;; esac\n',
    )
    install_dir = tmp_path / "install"
    env = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "OPENCODE_PROJECT_INSTALL_DIR": str(install_dir),
    }

    result = subprocess.run(
        ["sh", str(CLI_ROOT / "install.sh")], env=env, capture_output=True, text=True,
    )

    assert result.returncode != 0
    assert "Unsupported" in result.stderr
    assert not install_dir.exists()


@pytest.mark.skipif(
    os.name != "nt" and shutil.which("powershell.exe") is None,
    reason="PowerShell is needed to exercise the Windows installer",
)
def test_powershell_installer_downloads_and_installs_windows_binary(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    asset_log = tmp_path / "downloaded-url"
    script_path = str(CLI_ROOT / "install.ps1")
    if os.name != "nt":
        install_dir = Path(subprocess.run(
            ["wslpath", "-w", str(install_dir)], capture_output=True, text=True, check=True,
        ).stdout.strip())
        asset_log = Path(subprocess.run(
            ["wslpath", "-w", str(asset_log)], capture_output=True, text=True, check=True,
        ).stdout.strip())
        script_path = subprocess.run(
            ["wslpath", "-w", script_path], capture_output=True, text=True, check=True,
        ).stdout.strip()
    harness = (
        "$ErrorActionPreference = 'Stop'; "
        "$oldUserPath = [Environment]::GetEnvironmentVariable('Path', 'User'); "
        f"$env:OPENCODE_PROJECT_INSTALL_DIR = {_powershell_literal(str(install_dir))}; "
        f"$env:OPENCODE_PROJECT_TEST_ASSET_LOG = {_powershell_literal(str(asset_log))}; "
        "$env:OPENCODE_PROJECT_RELEASE_URL = 'https://releases.example/latest/download'; "
        "function Invoke-WebRequest { param($Uri, $OutFile); "
        "[System.IO.File]::WriteAllText($OutFile, 'binary'); "
        "[System.IO.File]::WriteAllText($env:OPENCODE_PROJECT_TEST_ASSET_LOG, $Uri) }; "
        "try { "
        f". {_powershell_literal(script_path)}; "
        "} finally { [Environment]::SetEnvironmentVariable('Path', $oldUserPath, 'User') }"
    )

    result = subprocess.run(
        [shutil.which("powershell") or shutil.which("powershell.exe"),
         "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", harness],
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    if os.name != "nt":
        install_dir = Path(subprocess.run(
            ["wslpath", "-u", str(install_dir)], capture_output=True, text=True, check=True,
        ).stdout.strip())
        asset_log = Path(subprocess.run(
            ["wslpath", "-u", str(asset_log)], capture_output=True, text=True, check=True,
        ).stdout.strip())
    assert asset_log.read_text(encoding="utf-8").strip().endswith("/opencode-project-windows-x64.exe")
    assert (install_dir / "opencode-project.exe").read_bytes() == b"binary"
