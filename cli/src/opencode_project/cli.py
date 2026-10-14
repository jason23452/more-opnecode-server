from __future__ import annotations

import argparse
import sys
import contextlib
from pathlib import Path

from opencode_project.connect import connect_terminal
from opencode_project.upload import create_archive, git_https_credentials, upload_archive, upload_git_credentials


def prompt_git_credentials(remote: str, credentials_available: bool) -> str:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return "upload"
    from urllib.parse import urlsplit

    parsed = urlsplit(remote)
    safe_remote = f"{parsed.scheme}://{parsed.hostname or ''}{parsed.path}"
    print(f"偵測到 HTTPS Git remote：{safe_remote}")
    if credentials_available:
        print("本機 Git credential helper 已提供認證（帳密/token 已遮蔽）。")
        print("[1] 傳送認證並上傳  [2] 只上傳專案（不帶認證）  [3] 取消")
    else:
        print("本機 Git credential helper 無法提供此 remote 的認證。")
        print("[2] 只上傳專案（不帶認證）  [3] 取消")
    choice = input("請選擇 [1/2/3]：").strip()
    return {"1": "send", "2": "upload", "3": "cancel"}.get(choice, "cancel")


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        encoding = getattr(stream, "encoding", None)
        if reconfigure is not None and encoding and encoding.lower().replace("-", "") != "utf8":
            reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    _configure_console_encoding()
    parser = argparse.ArgumentParser(prog="opencode-project", description="上傳專案資料夾至 OpenCode 容器")
    subcommands = parser.add_subparsers(dest="command", required=True)
    upload = subcommands.add_parser("upload", help="上傳專案資料夾")
    upload.add_argument("--url", required=True, help="建立容器回應中的 upload_url")
    upload.add_argument("--token", required=True, help="建立容器回應中的 upload_token")
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
        git_auth = git_https_credentials(args.project)
        decision = "upload"
        if git_auth:
            remote, credentials = git_auth
            decision = prompt_git_credentials(remote, bool(credentials))
            if decision == "cancel":
                print("已取消上傳。")
                return
            if decision == "send" and not credentials:
                decision = "upload"
        archive = create_archive(args.project)
        try:
            upload_archive(args.url, args.token, archive, retries=args.retries)
            if decision == "send" and git_auth:
                upload_git_credentials(args.url, args.token, git_auth[0], git_auth[1], retries=args.retries)
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
