from __future__ import annotations

import argparse
import sys
import contextlib
from pathlib import Path

from opencode_project.connect import connect_terminal
from opencode_project.upload import create_archive, upload_archive


def main() -> None:
    parser = argparse.ArgumentParser(prog="opencode-project", description="上傳專案資料夾至 OpenCode 容器")
    subcommands = parser.add_subparsers(dest="command", required=True)
    upload = subcommands.add_parser("upload", help="上傳專案資料夾")
    upload.add_argument("--url", required=True, help="建立容器回應中的 upload_url")
    upload.add_argument("--token", required=True, help="建立容器回應中的 upload_token")
    upload.add_argument("--refresh-url", help="建立容器回應中的 upload_target_url（Tunnel URL 更新時刷新）")
    upload.add_argument("--project", type=Path, default=Path.cwd(), help="本機專案資料夾（預設為目前目錄）")
    upload.add_argument("--retries", type=int, default=3, help="傳輸重試次數（預設 3）")
    upload.add_argument("--connect-url", help="上傳完成後連線至遠端 TUI")
    upload.add_argument("--connect-token", help="容器專屬 TUI 連線授權")
    connect = subcommands.add_parser("connect", help="連入遠端 OpenCode TUI")
    connect.add_argument("--url", required=True, help="建立容器回應中的 connect_url")
    connect.add_argument("--token", required=True, help="建立容器回應中的 connect_token")
    args = parser.parse_args()
    try:
        if args.command == "connect":
            connect_terminal(args.url, args.token)
            return
        if bool(args.connect_url) != bool(args.connect_token):
            raise ValueError("--connect-url 與 --connect-token 必須一起提供")
        archive = create_archive(args.project)
        try:
            upload_archive(args.url, args.token, archive, retries=args.retries, refresh_url=args.refresh_url)
        finally:
            if isinstance(archive, Path):
                with contextlib.suppress(FileNotFoundError):
                    archive.unlink()
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
    print("專案已上傳至容器工作目錄 /workspace/project")
    if args.connect_url:
        connect_terminal(args.connect_url, args.connect_token)


if __name__ == "__main__":
    main()
