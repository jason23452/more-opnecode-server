from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
import shutil
import stat
import ctypes
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

MAX_UPLOAD_BYTES = 95 * 1024 * 1024
MAX_ENTRIES = 100_000
MAX_EXPANDED_BYTES = 2 * 1024**3
PROJECT = Path("/workspace/project")
_INSTALL_LOCK = threading.Lock()
_SESSION_LOCK = threading.RLock()
CHUNK_BYTES = 8 * 1024 * 1024
MAX_SINGLE_UPLOAD_BYTES = 95 * 1024 * 1024


@dataclass(frozen=True)
class UploadManifest:
    size: int
    chunks: int
    sha256: str


def _exchange_directories(left: Path, right: Path) -> None:
    """Atomically exchange two same-filesystem directory entries (Linux)."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(left), -100, os.fsencode(right), 2) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
SESSION_TTL_SECONDS = 24 * 60 * 60


class UploadSessions:
    """容器內暫存並驗證分塊封裝，驗證完成後才替換工作目錄。"""

    def __init__(self, target: Path, root: Path, max_bytes: int = 2 * 1024**3):
        self.target = target
        self.root = root
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = _SESSION_LOCK
        self.cleanup_stale()

    def cleanup_stale(self) -> None:
        cutoff = time.time() - SESSION_TTL_SECONDS
        for entry in self.root.iterdir():
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                continue

    def create(self, client_id: str, manifest: UploadManifest) -> str:
        if not re.fullmatch(r"[0-9a-f]{32}", client_id):
            raise ValueError("Invalid upload session ID")
        if manifest.size <= 0 or manifest.size > self.max_bytes or manifest.chunks <= 0 or manifest.chunks > 100_000:
            raise ValueError("Invalid upload size or chunk count")
        if not re.fullmatch(r"[0-9a-f]{64}", manifest.sha256):
            raise ValueError("Invalid archive digest")
        if manifest.chunks != (manifest.size + CHUNK_BYTES - 1) // CHUNK_BYTES:
            raise ValueError("Invalid chunk count for archive size")
        session = client_id
        directory = self.root / session
        with self.lock:
            if directory.exists():
                if json.loads((directory / "metadata.json").read_text()) != asdict(manifest):
                    raise ValueError("Upload session metadata conflict")
                return session
            directory.mkdir(mode=0o700)
            (directory / "metadata.json").write_text(json.dumps(asdict(manifest)))
        return session

    def _session(self, session: str) -> tuple[Path, UploadManifest]:
        if not re.fullmatch(r"[0-9a-f]{32}", session):
            raise ValueError("Invalid upload session")
        directory = self.root / session
        manifest = UploadManifest(**json.loads((directory / "metadata.json").read_text()))
        return directory, manifest

    def put_chunk(self, session: str, index: int, data: bytes, digest: str) -> None:
        with self.lock:
            directory, metadata = self._session(session)
            if index < 0 or index >= metadata.chunks:
                raise ValueError("Invalid chunk index")
            expected_size = min(CHUNK_BYTES, metadata.size - index * CHUNK_BYTES)
            if len(data) != expected_size or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Corrupt chunk")
            destination = directory / f"{index}.chunk"
            if destination.exists():
                if destination.read_bytes() != data:
                    raise ValueError("Chunk conflict")
                return
            temporary = directory / f".{index}.{uuid.uuid4().hex}.tmp"
            temporary.write_bytes(data)
            os.replace(temporary, destination)

    def finalize(self, session: str) -> None:
        with self.lock, _INSTALL_LOCK:
            directory, metadata = self._session(session)
            paths = [directory / f"{index}.chunk" for index in range(metadata.chunks)]
            if not all(path.is_file() for path in paths):
                raise ValueError("Missing upload chunks")
            digest = hashlib.sha256()
            total = 0
            for path in paths:
                with path.open("rb") as chunk:
                    for block in iter(lambda: chunk.read(1024 * 1024), b""):
                        digest.update(block)
                        total += len(block)
            if total != metadata.size or digest.hexdigest() != metadata.sha256:
                raise ValueError("Archive size or digest mismatch")
            with tempfile.TemporaryFile(dir=self.root) as archive_file:
                for path in paths:
                    with path.open("rb") as chunk:
                        shutil.copyfileobj(chunk, archive_file, 1024 * 1024)
                archive_file.flush()
                install_archive(Path(f"/proc/self/fd/{archive_file.fileno()}"), self.target, max_bytes=self.max_bytes)
            shutil.rmtree(directory)


def install_archive(data: bytes | Path, target: Path, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    source_path = data if isinstance(data, Path) else None
    if source_path is not None and source_path.stat().st_size > max_bytes or isinstance(data, bytes) and len(data) > max_bytes:
        raise ValueError(f"Project archive exceeds the single-request limit of {max_bytes} bytes")
    try:
        with zipfile.ZipFile(source_path if source_path is not None else __import__("io").BytesIO(data)) as archive:
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
            _cleanup_stale_project_backups(parent)
            staging = Path(tempfile.mkdtemp(prefix=".project-backup-", dir=parent))
            backup: Path | None = None
            retain_backup = False
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
                    _exchange_directories(staging, target)
                    backup = staging
                else:
                    os.replace(staging, target)
                if backup is not None:
                    try:
                        shutil.rmtree(backup)
                    except OSError:
                        # The exchange has committed: keep the verified target authoritative.
                        # A partially removed old tree stays named as a backup for later cleanup.
                        retain_backup = True
            finally:
                if staging.exists() and not retain_backup:
                    shutil.rmtree(staging)
    except (zipfile.BadZipFile, OSError, RuntimeError) as error:
        raise ValueError("Invalid project archive") from error


def _cleanup_stale_project_backups(parent: Path) -> None:
    cutoff = time.time() - SESSION_TTL_SECONDS
    for backup in parent.glob(".project-backup-*"):
        try:
            if backup.stat().st_mtime < cutoff:
                shutil.rmtree(backup, ignore_errors=True)
        except OSError:
            continue


class UploadHandler(BaseHTTPRequestHandler):
    server_version = "ProjectUpload/1"

    @property
    def sessions(self) -> UploadSessions:
        root = Path(os.environ.get("OPENCODE_UPLOAD_SESSION_DIR", "/tmp/opencode-upload-sessions"))
        return UploadSessions(PROJECT, root, max_bytes=int(os.environ.get("OPENCODE_UPLOAD_MAX_PROJECT_BYTES", 2 * 1024**3)))

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + os.environ.get("OPENCODE_UPLOAD_TOKEN", "")
        if not os.environ.get("OPENCODE_UPLOAD_TOKEN") or not hmac.compare_digest(supplied, expected):
            self.send_error(401, "Invalid container upload token")
            return False
        return True

    def _body(self, limit: int) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0:
            self.send_error(411, "Content-Length is required")
            return None
        if length > limit:
            self.send_error(413, "Upload request exceeds chunk limit")
            return None
        data = self.rfile.read(length)
        if len(data) != length:
            self.send_error(400, "Incomplete request body")
            return None
        return data

    def _json(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        if self.path == "/upload/sessions":
            data = self._body(4096)
            if data is None:
                return
            try:
                payload = json.loads(data)
                manifest = UploadManifest(int(payload["size"]), int(payload["chunks"]), payload["sha256"])
                session = self.sessions.create(payload["session_id"], manifest)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                self.send_error(400, str(error))
                return
            self._json({"session_id": session})
            return
        match = re.fullmatch(r"/upload/sessions/([0-9a-f]{32})/finalize", self.path)
        if match:
            try:
                self.sessions.finalize(match.group(1))
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                self.send_error(400, str(error))
                return
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)

    def do_PUT(self) -> None:
        if not self._authorized():
            return
        match = re.fullmatch(r"/upload/sessions/([0-9a-f]{32})/chunks/(\d+)", self.path)
        if match:
            data = self._body(CHUNK_BYTES)
            if data is None:
                return
            try:
                self.sessions.put_chunk(match.group(1), int(match.group(2)), data, self.headers.get("X-Chunk-SHA256", ""))
            except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
                self.send_error(400, str(error))
                return
            self.send_response(204)
            self.end_headers()
            return

        if self.path != "/upload":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        limit = min(int(os.environ.get("OPENCODE_UPLOAD_MAX_BYTES", MAX_SINGLE_UPLOAD_BYTES)), MAX_SINGLE_UPLOAD_BYTES)
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
