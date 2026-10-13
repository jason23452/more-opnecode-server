# 10: 移除 CLI 對內網管理 API 的連線依賴

**What to build:** 讓本機 CLI 的上傳與 TUI 操作只呼叫容器 Tunnel；管理者仍可透過內網管理 API 查詢目前的 Tunnel URL，並手動重新提供 CLI 命令。

**Blocked by:**
- 08: 分塊重試並刷新 Tunnel 上傳目標.
- 09: 透過容器 Tunnel 直接連入遠端 TUI.

**Status:** resolved

- [x] 列表/單筆管理查詢回傳目前的 Tunnel `upload_url` 與 `connect_url`，但不回傳 upload/connect token；管理 API 仍受管理者授權保護。
- [x] CLI 不再呼叫後端 `upload-target` 控制 endpoint，也不需要 `localhost:8000`；專案封裝區塊與 TUI WebSocket 全部直接連至容器 Tunnel。
- [x] CLI 遇到過期 Tunnel URL 時停止並提示使用者從內網管理 API 取得最新 URL，再使用原容器 token 重新執行命令；不嘗試自動連回後端。
- [x] 移除後端 per-container upload-target 查詢 endpoint，以及 CLI `--refresh-url` 選項與自動刷新流程。
- [x] 以測試確認 CLI 的 upload/connect 操作只呼叫 Tunnel URL；另驗證管理查詢可提供新的 Tunnel 目標，使用者重新執行命令後可完成上傳與 TUI 連線。

## Answer

- 管理列表與單筆 GET 以目前的 Tunnel base URL 產生 `upload_url`/`connect_url`，並沿用 admin bearer 授權；回應不含容器 token。
- 移除 `upload-target` endpoint、`ContainerManager.upload_target`、建立回應中的 `upload_target_url`、CLI `--refresh-url` 及自動刷新程式碼。CLI 上傳/TUI 失敗時明確提示管理端重查 URL 並沿用原 token。
- 驗證通過：後端 `uv run pytest`（60 passed、2 skipped）、CLI `uv run --with pytest pytest`（15 passed）、`uv run python -m compileall -q src`、shell/PowerShell 語法檢查、PyInstaller 單檔建置與 `--help`。
- Docker/Quick Tunnel 驗收通過：`OPENCODE_DOCKER_E2E=1` 之 96 MiB stale-URL 手動重查/重試 E2E（1 passed）；測試涵蓋原 token、管理回應無 token、直接 TUI、跨容器隔離與清理。使用 WSL PATH 中的原生 Docker Desktop `docker.exe`（CLI 自動偵測）。
- 整合驗證：後端 `uv run pytest`（60 passed、2 skipped）、CLI `uv run --with pytest pytest`（15 passed）、`uv run python -m compileall -q src`、Bash `bash -n`、`git diff --check`，以及上述 Docker/Quick Tunnel E2E（1 passed）；Docker CLI 自動解析為原生 `docker.exe` 並連上 Docker Desktop。
