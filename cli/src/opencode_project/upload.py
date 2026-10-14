from __future__ import annotations

import hashlib
import json
import os
import ssl
import tempfile
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .tls import create_ssl_context

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
    with _open_url(request) as response:
        return response.status


def _open_url(request: Request):
    return urlopen(request, timeout=300, context=create_ssl_context())


def _request(url: str, token: str, data: bytes | None = None, method: str = "GET", headers: dict[str, str] | None = None) -> bytes:
    request = Request(url, data=data, headers={"Authorization": f"Bearer {token}", **(headers or {})}, method=method)
    with _open_url(request) as response:
        return response.read()


def _retry_request(operation, retries: int, current_url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            return operation(current_url)
        except (OSError, URLError, HTTPError, RuntimeError, ValueError) as error:
            last_error = error
            if attempt + 1 >= retries:
                break
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(_upload_failure_message(last_error)) from last_error


def _upload_failure_message(error: Exception | None) -> str:
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, ssl.SSLCertVerificationError):
        return (
            f"Tunnel TLS 憑證驗證失敗：{reason}。CLI 使用內建公開 CA 憑證；"
            "若網路使用自訂或公司 TLS 憑證，請將 SSL_CERT_FILE 設為受信任的 CA 憑證檔後重試。"
        )
    return (
        f"Tunnel 上傳失敗：{error}。請透過管理 API 重新查詢目前的 upload_url，"
        "並使用原容器 upload token 重新執行上傳命令。"
    )


def upload_archive(url: str, token: str, archive: bytes | Path, retries: int = 3) -> None:
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
        response = _retry_request(
            lambda target: _request(target + "/upload/sessions", token, metadata, "POST", {"Content-Type": "application/json"}),
            retries, current_url,
        )
        session = json.loads(response)["session_id"]
        with archive_path.open("rb") if archive_path else __import__("io").BytesIO(archive) as source:
            for index in range((size + CHUNK_BYTES - 1) // CHUNK_BYTES):
                chunk = source.read(CHUNK_BYTES)
                chunk_digest = hashlib.sha256(chunk).hexdigest()
                _retry_request(
                    lambda target, i=index, part=chunk, sha=chunk_digest: _request(
                        f"{target}/upload/sessions/{session}/chunks/{i}", token, part, "PUT",
                        {"Content-Type": "application/octet-stream", "X-Chunk-SHA256": sha}),
                    retries, current_url,
                )
        _retry_request(
            lambda target: _request(target + f"/upload/sessions/{session}/finalize", token, b"", "POST"),
            retries, current_url,
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
    raise RuntimeError(_upload_failure_message(last_error)) from last_error
