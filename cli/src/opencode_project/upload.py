from __future__ import annotations

import io
import hashlib
import json
import os
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXCLUDED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
    ".next", ".nuxt", "dist", "build", "target", "coverage",
}
MAX_UPLOAD_BYTES = 95 * 1024 * 1024
CHUNK_BYTES = 8 * 1024 * 1024


def create_archive(project: Path) -> bytes:
    root = project.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"專案資料夾不存在：{root}")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
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
    return output.getvalue()


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


def upload_archive(url: str, token: str, archive: bytes, retries: int = 3, refresh_url: str | None = None) -> None:
    if len(archive) > 2 * 1024**3:
        raise ValueError("專案封裝檔超過 2 GiB 上限，請縮小專案後重試。")
    if len(archive) > MAX_UPLOAD_BYTES:
        current_url = url.removesuffix("/upload")
        metadata = json.dumps({"size": len(archive), "chunks": (len(archive) + CHUNK_BYTES - 1) // CHUNK_BYTES,
                               "sha256": hashlib.sha256(archive).hexdigest()}).encode()
        response, current_url = _retry_request(
            lambda target: _request(target + "/upload/sessions", token, metadata, "POST", {"Content-Type": "application/json"}),
            retries, refresh_url, token, current_url,
        )
        session = json.loads(response)["session_id"]
        for index, offset in enumerate(range(0, len(archive), CHUNK_BYTES)):
            chunk = archive[offset:offset + CHUNK_BYTES]
            digest = hashlib.sha256(chunk).hexdigest()
            _, current_url = _retry_request(
                lambda target, i=index, part=chunk, sha=digest: _request(
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
            status = _send(url, token, archive)
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
