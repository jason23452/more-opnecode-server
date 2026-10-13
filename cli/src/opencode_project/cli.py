from __future__ import annotations

import argparse
import sys
from pathlib import Path

from opencode_project.upload import create_archive, upload_archive


def main() -> None:
    parser = argparse.ArgumentParser(prog="opencode-project", description="上傳專案資料夾至 OpenCode 容器")
    subcommands = parser.add_subparsers(dest="command", required=True)
    upload = subcommands.add_parser("upload", help="上傳專案資料夾")
    upload.add_argument("--url", required=True, help="建立容器回應中的 upload_url")
    upload.add_argument("--token", required=True, help="建立容器回應中的 upload_token")
    upload.add_argument("--project", type=Path, default=Path.cwd(), help="本機專案資料夾（預設為目前目錄）")
    upload.add_argument("--retries", type=int, default=3, help="傳輸重試次數（預設 3）")
    args = parser.parse_args()
    try:
        archive = create_archive(args.project)
        upload_archive(args.url, args.token, archive, retries=args.retries)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    print("專案已上傳至容器工作目錄 /workspace/project")


if __name__ == "__main__":
    main()
