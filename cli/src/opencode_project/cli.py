from __future__ import annotations

import argparse
import sys
import contextlib
from enum import Enum
from pathlib import Path

from opencode_project.connect import connect_terminal
from opencode_project.upload import (
    create_archive, git_https_credentials, git_ssh_credentials, sanitize_remote, upload_archive,
    upload_git_credentials,
)


class GitCredentialPromptChoice(str, Enum):
    SEND = "send"
    PROCEED_WITHOUT_CREDENTIALS = "proceed_without_credentials"
    CANCEL = "cancel"


def prompt_git_credential_transfer(
    remote: str,
    credentials_available: bool,
    auth_type: str = "HTTPS Git credential helper",
    purpose: str = "upload",
) -> GitCredentialPromptChoice:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return GitCredentialPromptChoice.PROCEED_WITHOUT_CREDENTIALS
    safe_remote = sanitize_remote(remote)
    print(f"偵測到 {auth_type.split(':', 1)[0]} Git remote：{safe_remote}")
    if purpose == "connect":
        if credentials_available:
            print("本機 SSH agent 已提供認證；只會在這次 CLI 連線期間轉送簽章請求。")
            print("[1] 連線並啟用 SSH agent 轉送  [2] 只連線（不轉送）  [3] 取消")
        else:
            print("本機無法取得此 remote 的 SSH agent 認證。")
            print("[2] 只連線（不轉送）  [3] 取消")
        choice = input("請選擇 [1/2/3]：").strip()
        return {
            "1": GitCredentialPromptChoice.SEND,
            "2": GitCredentialPromptChoice.PROCEED_WITHOUT_CREDENTIALS,
            "3": GitCredentialPromptChoice.CANCEL,
        }.get(choice, GitCredentialPromptChoice.CANCEL)
    if credentials_available:
        print(f"本機 {auth_type} 已提供認證（秘密內容已遮蔽）。")
        print("[1] 傳送認證並上傳  [2] 只上傳專案（不帶認證）  [3] 取消")
    else:
        print(f"本機無法取得此 remote 的 {auth_type} 認證。")
        print("[2] 只上傳專案（不帶認證）  [3] 取消")
    choice = input("請選擇 [1/2/3]：").strip()
    return {
        "1": GitCredentialPromptChoice.SEND,
        "2": GitCredentialPromptChoice.PROCEED_WITHOUT_CREDENTIALS,
        "3": GitCredentialPromptChoice.CANCEL,
    }.get(choice, GitCredentialPromptChoice.CANCEL)


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
    connect.add_argument("--project", type=Path, default=Path.cwd(), help="已上傳的本機 Git 專案（預設為目前目錄）")
    args = parser.parse_args()
    try:
        if args.command == "connect":
            ssh_auth = git_ssh_credentials(args.project)
            forward_agent = False
            if ssh_auth:
                credentials_available = bool(ssh_auth[1].get("agent_forwarding"))
                decision = prompt_git_credential_transfer(
                    ssh_auth[0], credentials_available, "SSH agent forwarding", purpose="connect",
                )
                if decision == "cancel":
                    print("已取消連線。")
                    return
                forward_agent = decision == "send" and credentials_available
            connect_terminal(args.url, args.token, forward_ssh_agent=forward_agent)
            return
        if bool(args.connect_url) != bool(args.connect_token):
            raise ValueError("--connect-url 與 --connect-token 必須一起提供")
        git_auth = git_https_credentials(args.project)
        auth_type = "HTTPS Git credential helper"
        if git_auth is None:
            git_auth = git_ssh_credentials(args.project)
            auth_type = "SSH agent forwarding"
        decision = "upload"
        if git_auth:
            remote, credentials = git_auth
            credentials_available = bool(credentials) and "unsupported" not in credentials
            decision = (prompt_git_credential_transfer(remote, credentials_available)
                        if auth_type == "HTTPS Git credential helper"
                        else prompt_git_credential_transfer(remote, credentials_available, auth_type))
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
    if decision == "send" and git_auth and auth_type == "SSH agent forwarding":
        print("SSH agent 僅會在本機 CLI connect 工作階段連線期間即時轉送；私鑰不會離開本機。")
    if args.connect_url:
        forward_agent = bool(
            decision == "send" and git_auth and auth_type == "SSH agent forwarding"
            and git_auth[1].get("agent_forwarding")
        )
        connect_terminal(args.connect_url, args.connect_token, forward_ssh_agent=forward_agent)


if __name__ == "__main__":
    main()
