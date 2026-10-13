from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXCLUDED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
    ".next", ".nuxt", "dist", "build", "target", "coverage",
}
MAX_UPLOAD_BYTES = 95 * 1024 * 1024
CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class UploadMetadata:
    session_id: str
    size: int
    chunks: int
    sha256: str


def create_archive(project: Path) -> Path:
    root = project.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"專案資料夾不存在：{root}")
    output = tempfile.NamedTemporaryFile(prefix="opencode-project-", suffix=".zip", delete=False)
    output_path = Path(output.name)
    output.close()
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            directories[:] = sorted(
                name for name in directories
                if name not in EXCLUDED_DIRECTORIES and not (current_path / name).is_symlink()
            )
            for name in sorted(files):
                path = current_path / name
                if path.is_symlink() or not path.is_file():
                    continue
                archive.write(path, path.relative_to(root).as_posix())
    return output_path


def _send(url: str, token: str, archive: bytes) -> int:
    request = Request(
        url,
        data=archive,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
        method="PUT",
    )
    with urlopen(request, timeout=300) as response:
        return response.status


def _request(url: str, token: str, data: bytes | None = None, method: str = "GET", headers: dict[str, str] | None = None) -> bytes:
    request = Request(url, data=data, headers={"Authorization": f"Bearer {token}", **(headers or {})}, method=method)
    with urlopen(request, timeout=300) as response:
        return response.read()


def _refresh_target(refresh_url: str, token: str) -> str:
    payload = json.loads(_request(refresh_url, token))
    target = payload.get("upload_url")
    if not isinstance(target, str) or not target.startswith(("https://", "http://")):
        raise RuntimeError("Tunnel upload target refresh returned an invalid URL")
    return target.removesuffix("/upload")


def _retry_request(operation, retries: int, refresh_url: str | None, token: str, current_url: str) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            return operation(current_url), current_url
        except (OSError, URLError, HTTPError, RuntimeError, ValueError) as error:
            last_error = error
            if attempt + 1 >= retries:
                break
            if refresh_url:
                try:
                    current_url = _refresh_target(refresh_url, token)
                except (OSError, URLError, HTTPError, ValueError, RuntimeError) as refresh_error:
                    last_error = refresh_error
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"上傳失敗，請再次執行相同命令重試：{last_error}") from last_error


def upload_archive(url: str, token: str, archive: bytes | Path, retries: int = 3, refresh_url: str | None = None) -> None:
    archive_path = archive if isinstance(archive, Path) else None
    size = archive_path.stat().st_size if archive_path else len(archive)
    if size > 2 * 1024**3:
        raise ValueError("專案封裝檔超過 2 GiB 上限，請縮小專案後重試。")
    if size > MAX_UPLOAD_BYTES or archive_path is not None:
        current_url = url.removesuffix("/upload")
        digest = hashlib.sha256()
        if archive_path:
            with archive_path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
        else:
            digest.update(archive)
        metadata = json.dumps(asdict(UploadMetadata(uuid.uuid4().hex, size, (size + CHUNK_BYTES - 1) // CHUNK_BYTES,
                                                     digest.hexdigest()))).encode()
        response, current_url = _retry_request(
            lambda target: _request(target + "/upload/sessions", token, metadata, "POST", {"Content-Type": "application/json"}),
            retries, refresh_url, token, current_url,
        )
        session = json.loads(response)["session_id"]
        with archive_path.open("rb") if archive_path else __import__("io").BytesIO(archive) as source:
            for index in range((size + CHUNK_BYTES - 1) // CHUNK_BYTES):
                chunk = source.read(CHUNK_BYTES)
                chunk_digest = hashlib.sha256(chunk).hexdigest()
                _, current_url = _retry_request(
                    lambda target, i=index, part=chunk, sha=chunk_digest: _request(
                        f"{target}/upload/sessions/{session}/chunks/{i}", token, part, "PUT",
                        {"Content-Type": "application/octet-stream", "X-Chunk-SHA256": sha}),
                    retries, refresh_url, token, current_url,
                )
        _retry_request(
            lambda target: _request(target + f"/upload/sessions/{session}/finalize", token, b"", "POST"),
            retries, refresh_url, token, current_url,
        )
        return
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            payload = archive_path.read_bytes() if archive_path else archive
            status = _send(url, token, payload)
            if status != 204:
                raise RuntimeError(f"上傳失敗：HTTP {status}")
            return
        except (OSError, URLError, HTTPError, RuntimeError) as error:
            if isinstance(error, HTTPError) and error.code == 413:
                raise ValueError(
                    "專案封裝檔超過 Tunnel 單次上傳限制（HTTP 413）；請縮小專案後重試。"
                ) from error
            last_error = error
            if attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"上傳失敗，請再次執行相同命令重試：{last_error}") from last_error
