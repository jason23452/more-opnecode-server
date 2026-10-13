"""Read a local clipboard image for a remote OpenCode TUI session."""

from __future__ import annotations

import base64
import mimetypes
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_CLIPBOARD_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CLIPBOARD_FILE_BYTES = 25 * 1024 * 1024
MAX_CLIPBOARD_FILES = 16
MAX_CLIPBOARD_BATCH_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class ClipboardImage:
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class ClipboardFile:
    name: str
    mime_type: str
    data: bytes


_IMAGE_TYPES = {
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/webp": (".webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
    "image/gif": (".gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
}


def _validated_image(mime_type: str, data: bytes) -> ClipboardImage | None:
    image_type = _IMAGE_TYPES.get(mime_type)
    if not image_type or len(data) > MAX_CLIPBOARD_IMAGE_BYTES or not image_type[1](data):
        return None
    return ClipboardImage(mime_type, data)


def _read_windows_image() -> ClipboardImage | None:
    executable = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh.exe")
    if not executable:
        return None
    script = (
        "$ErrorActionPreference='Stop'; "
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$image=[System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($null -eq $image) { exit 2 }; "
        "$stream=New-Object System.IO.MemoryStream; "
        "$image.Save($stream,[System.Drawing.Imaging.ImageFormat]::Png); "
        "[Console]::Out.Write([Convert]::ToBase64String($stream.ToArray()))"
    )
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-STA", "-Command", script],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        return _validated_image("image/png", base64.b64decode(result.stdout, validate=True))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _read_macos_image() -> ClipboardImage | None:
    executable = shutil.which("osascript")
    if not executable:
        return None
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="opencode-clipboard-", suffix=".png", delete=False) as target:
            path = target.name
        escaped_path = path.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            "set imageData to (the clipboard as «class PNGf»)\n"
            f'set outputFile to open for access (POSIX file "{escaped_path}") with write permission\n'
            "set eof outputFile to 0\n"
            "write imageData to outputFile\n"
            "close access outputFile\n"
        )
        result = subprocess.run([executable, "-e", script], capture_output=True, timeout=5)
        if result.returncode != 0:
            return None
        return _validated_image("image/png", Path(path).read_bytes())
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _read_linux_image() -> ClipboardImage | None:
    candidates = []
    if shutil.which("wl-paste"):
        candidates.append(("wl-paste", ["wl-paste", "--no-newline", "--type"]))
    if shutil.which("xclip"):
        candidates.append(("xclip", ["xclip", "-selection", "clipboard", "-t"]))

    for mime_type in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        for executable, prefix in candidates:
            suffix = [mime_type] if executable == "wl-paste" else [mime_type, "-o"]
            try:
                result = subprocess.run([*prefix, *suffix], capture_output=True, timeout=3)
            except (OSError, subprocess.SubprocessError):
                continue
            if result.returncode == 0:
                image = _validated_image(mime_type, result.stdout)
                if image:
                    return image
    return None


def read_clipboard_image() -> ClipboardImage | None:
    """Return a supported image from the local OS clipboard, if present."""
    system = platform.system()
    if system == "Windows":
        return _read_windows_image()
    if system == "Darwin":
        return _read_macos_image()
    if system == "Linux":
        image = _read_linux_image()
        if image:
            return image
        # WSLg can expose the Windows clipboard through PowerShell even when
        # the Linux clipboard tools are not installed.
        if "microsoft" in platform.release().lower():
            return _read_windows_image()
    return None


def _decode_base64_path_lines(output: str) -> list[str]:
    paths = []
    for line in output.splitlines():
        try:
            paths.append(base64.b64decode(line, validate=True).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
    return paths


def _read_windows_file_paths() -> list[str]:
    executable = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh.exe")
    if not executable:
        return []
    script = (
        "$ErrorActionPreference='Stop'; "
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$files=[System.Windows.Forms.Clipboard]::GetFileDropList(); "
        "foreach ($path in $files) { "
        "[Console]::Out.WriteLine([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($path))) "
        "}"
    )
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-STA", "-Command", script],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return _decode_base64_path_lines(result.stdout) if result.returncode == 0 else []


def _read_macos_file_paths() -> list[str]:
    executable = shutil.which("osascript")
    if not executable:
        return []
    script = r'''
set encodedPaths to ""
try
    set clipboardItems to the clipboard as list
on error
    set clipboardItems to {the clipboard}
end try
repeat with clipboardItem in clipboardItems
    try
        set filePath to POSIX path of (contents of clipboardItem as alias)
        set encodedPath to do shell script "printf %s " & quoted form of filePath & " | /usr/bin/base64 | tr -d '\n'"
        set encodedPaths to encodedPaths & encodedPath & linefeed
    end try
end repeat
return encodedPaths
'''
    try:
        result = subprocess.run([executable, "-e", script], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return _decode_base64_path_lines(result.stdout) if result.returncode == 0 else []


def _parse_uri_list(value: str) -> list[str]:
    paths = []
    for line in value.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = urlparse(line)
        if parsed.scheme == "file" and parsed.path:
            paths.append(unquote(parsed.path))
    return paths


def _read_linux_file_paths() -> list[str]:
    if shutil.which("wl-paste"):
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline", "--type", "text/uri-list"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                paths = _parse_uri_list(result.stdout)
                if paths:
                    return paths
        except (OSError, subprocess.SubprocessError):
            pass
    if shutil.which("xclip"):
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return _parse_uri_list(result.stdout)
        except (OSError, subprocess.SubprocessError):
            pass
    return []


def _clipboard_files_from_paths(paths: list[str]) -> list[ClipboardFile]:
    files = []
    total_bytes = 0
    wsl_windows_paths = platform.system() == "Linux" and "microsoft" in platform.release().lower()
    for raw_path in paths:
        if len(files) >= MAX_CLIPBOARD_FILES or total_bytes >= MAX_CLIPBOARD_BATCH_BYTES:
            break
        path = raw_path
        if wsl_windows_paths and (len(path) > 2 and path[1] == ":"):
            converter = shutil.which("wslpath")
            if not converter:
                continue
            try:
                converted = subprocess.run([converter, "-u", path], capture_output=True, text=True, timeout=3)
            except (OSError, subprocess.SubprocessError):
                continue
            if converted.returncode != 0:
                continue
            path = converted.stdout.strip()
        try:
            source = Path(path)
            if not source.is_file():
                continue
            size = source.stat().st_size
            if size > MAX_CLIPBOARD_FILE_BYTES or total_bytes + size > MAX_CLIPBOARD_BATCH_BYTES:
                continue
            data = source.read_bytes()
        except OSError:
            continue
        files.append(ClipboardFile(source.name, mimetypes.guess_type(source.name)[0] or "application/octet-stream", data))
        total_bytes += len(data)
    return files


def read_clipboard_files() -> list[ClipboardFile]:
    """Read a clipboard image or copied regular files from the local OS."""
    system = platform.system()
    if system == "Windows":
        paths = _read_windows_file_paths()
    elif system == "Darwin":
        paths = _read_macos_file_paths()
    elif system == "Linux":
        paths = _read_linux_file_paths()
        if not paths and "microsoft" in platform.release().lower():
            paths = _read_windows_file_paths()
    else:
        paths = []
    files = _clipboard_files_from_paths(paths)
    if files:
        return files
    image = read_clipboard_image()
    if image:
        extension = _IMAGE_TYPES[image.mime_type][0]
        return [ClipboardFile(f"clipboard{extension}", image.mime_type, image.data)]
    return []
