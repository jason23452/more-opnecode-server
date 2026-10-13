from __future__ import annotations

import io
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


def upload_archive(url: str, token: str, archive: bytes, retries: int = 3) -> None:
    if len(archive) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"專案封裝檔超過單次上傳上限 95 MiB（目前 {len(archive) / 1024 / 1024:.1f} MiB）；"
            "請縮小專案後重試。大型專案分塊傳輸將由後續版本支援。"
        )
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
