# 03: 開啟容器並取得平台上傳與連線指令

**What to build:** 管理者可從既有容器清單開啟容器連線 URL，並在 Dashboard 選擇本機作業系統，查詢及複製該容器專屬的 CLI 連線指令，以連入遠端 TUI 工作階段。

**Blocked by:** 01: Dashboard 路由式分頁、驗證與容器清單.

**Status:** resolved

- [x] 容器清單提供以 `connect_url` 開啟新分頁的操作；此操作只開啟連線入口，不呼叫建立、停止或重啟 API。
- [x] 容器詳細資訊可選擇 macOS、Windows 或 Linux，並以既有單筆查詢 API 的 `mac`、`windows` 或 `linux` environment 參數取得對應命令。
- [x] 查詢請求使用目前頁面的 Bearer 管理 token，並呈現所選平台的 `upload_command` 與 `connect_command`。
- [x] 專案上傳與容器連線指令分開標示，且各自可複製並提供使用者可見回饋。
- [x] 查詢載入及失敗有明確狀態；401 沿用管理 token 無效提示及保留輸入值行為。
- [x] 頁面整合測試驗證新分頁連線目的地、平台參數、Bearer header、指令呈現/複製與錯誤狀態；不依賴真實 Tunnel。

## Answer

已整合至 `integration/container-management-dashboard`；連線 URL、專案上傳/容器連線平台指令查詢與分別複製均有頁面整合測試覆蓋，型別檢查與 production build 均通過。
