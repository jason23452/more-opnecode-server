# 10: 移除 CLI 對內網管理 API 的連線依賴

**What to build:** 讓本機 CLI 的上傳與 TUI 操作只呼叫容器 Tunnel；管理者仍可透過內網管理 API 查詢目前的 Tunnel URL，並手動重新提供 CLI 命令。

**Blocked by:**
- 08: 分塊重試並刷新 Tunnel 上傳目標.
- 09: 透過容器 Tunnel 直接連入遠端 TUI.

**Status:** ready-for-agent

- [ ] 列表/單筆管理查詢回傳目前的 Tunnel `upload_url` 與 `connect_url`，但不回傳 upload/connect token；管理 API 仍受管理者授權保護。
- [ ] CLI 不再呼叫後端 `upload-target` 控制 endpoint，也不需要 `localhost:8000`；專案封裝區塊與 TUI WebSocket 全部直接連至容器 Tunnel。
- [ ] CLI 遇到過期 Tunnel URL 時停止並提示使用者從內網管理 API 取得最新 URL，再使用原容器 token 重新執行命令；不嘗試自動連回後端。
- [ ] 移除後端 per-container upload-target 查詢 endpoint，以及 CLI `--refresh-url` 選項與自動刷新流程。
- [ ] 以測試確認 CLI 的 upload/connect 操作只呼叫 Tunnel URL；另驗證管理查詢可提供新的 Tunnel 目標，使用者重新執行命令後可完成上傳與 TUI 連線。
