from __future__ import annotations

import hmac
import io
import os
import shutil
import stat
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

MAX_UPLOAD_BYTES = 95 * 1024 * 1024
MAX_ENTRIES = 100_000
MAX_EXPANDED_BYTES = 2 * 1024**3
PROJECT = Path("/workspace/project")
_INSTALL_LOCK = threading.Lock()


def install_archive(data: bytes, target: Path, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    if len(data) > max_bytes:
        raise ValueError(f"Project archive exceeds the single-request limit of {max_bytes} bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES:
                raise ValueError("Project archive exceeds extraction limits")
            safe_entries = []
            for item in entries:
                relative = PurePosixPath(item.filename)
                mode = item.external_attr >> 16
                if relative.is_absolute() or ".." in relative.parts or "\x00" in item.filename or stat.S_ISLNK(mode):
                    raise ValueError("Unsafe project archive path")
                safe_entries.append((item, relative))

            target = target.resolve()
            parent = target.parent
            parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".project-upload-", dir=parent))
            backup: Path | None = None
            try:
                for item, relative in safe_entries:
                    destination = staging.joinpath(*relative.parts)
                    destination.resolve().relative_to(staging.resolve())
                    if item.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(item) as source, destination.open("wb") as output:
                            shutil.copyfileobj(source, output)
                if target.exists():
                    backup = Path(tempfile.mkdtemp(prefix=".project-backup-", dir=parent))
                    backup.rmdir()
                    os.replace(target, backup)
                try:
                    os.replace(staging, target)
                except Exception:
                    if backup is not None and backup.exists() and not target.exists():
                        os.replace(backup, target)
                    raise
                if backup is not None:
                    shutil.rmtree(backup)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
    except (zipfile.BadZipFile, OSError, RuntimeError) as error:
        raise ValueError("Invalid project archive") from error


class UploadHandler(BaseHTTPRequestHandler):
    server_version = "ProjectUpload/1"

    def do_PUT(self) -> None:
        if self.path != "/upload":
            self.send_error(404)
            return
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + os.environ.get("OPENCODE_UPLOAD_TOKEN", "")
        if not os.environ.get("OPENCODE_UPLOAD_TOKEN") or not hmac.compare_digest(supplied, expected):
            self.send_error(401, "Invalid container upload token")
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        limit = int(os.environ.get("OPENCODE_UPLOAD_MAX_BYTES", MAX_UPLOAD_BYTES))
        if length < 0:
            self.send_error(411, "Content-Length is required")
            return
        if length > limit:
            self.send_error(413, f"Project archive exceeds single-request limit ({limit} bytes)")
            return
        data = self.rfile.read(length)
        if len(data) != length:
            self.send_error(400, "Incomplete project archive")
            return
        try:
            with _INSTALL_LOCK:
                install_archive(data, PROJECT, max_bytes=limit)
        except ValueError as error:
            status = 413 if "limit" in str(error).lower() else 400
            self.send_error(status, str(error))
            return
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def serve() -> None:
    ThreadingHTTPServer(("0.0.0.0", 4097), UploadHandler).serve_forever()


if __name__ == "__main__":
    serve()
