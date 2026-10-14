# 05: CLI 工具安裝命令分頁

**What to build:** 使用者可從獨立的 CLI 工具路由分頁選擇本機作業系統，取得並複製 CLI 工具的下載/安裝命令，無須先建立 OpenCode 容器。

**Blocked by:** 01: Dashboard 路由式分頁、驗證與容器清單.

**Status:** resolved

- [x] Dashboard 導覽提供可直接進入的「CLI 工具」路由分頁。
- [x] 管理者可選擇 macOS、Windows 或 Linux，並使用目前頁面的 Bearer 管理 token 呼叫既有 `/opencode/cli-install-command` API，傳入對應的 `mac`、`windows` 或 `linux` environment。
- [x] API 回傳的 CLI 安裝命令清楚呈現並可複製；說明命令會下載/安裝 CLI 工具，而非提供直接下載檔案。
- [x] 請求進行中、錯誤及 401 管理 token 無效狀態均有明確回饋，且可修改 token 後重試。
- [x] 頁面整合測試驗證路由、平台參數、Bearer header、命令呈現及複製操作。

## Answer

已整合至 `integration/container-management-dashboard`；新增 CLI 工具安裝命令路由分頁，並以頁面整合測試驗證平台命令取得與複製。
