# 05: 透過本機 CLI 上傳專案資料夾至容器

**What to build:** 讓使用者使用本機專案 CLI 將指定的專案資料夾上傳至已建立的 OpenCode 容器，並能在中斷後重試。

**Blocked by:** 01: 建立並公開 OpenCode 容器.

**Status:** resolved

- [x] 建立 API 成功回應包含該容器專屬的 CLI 上傳指令與授權資訊；使用者無須在本機持有 Docker 權限或 OpenCode 管理密碼。
- [x] 使用者可安裝並執行獨立的本機專案 CLI，指定資料夾並將內容上傳至對應容器。
- [x] CLI 透過 GitHub Releases 提供 Windows x64、macOS Intel/Apple Silicon 與 Linux x64 獨立執行檔；安裝不要求 Python、uv 或 Node.js，建立 API 回應提供各平台安裝命令。
- [x] 上傳預設排除常見大型產物；上傳的專案檔案放入該容器專屬工作目錄，不影響其他容器。
- [x] 傳輸中斷後容器仍保留，CLI 可對同一容器重試；此上傳 CLI 不提供 TUI 連線操作。
- [x] 專案資料隨容器存續；刪除容器時一併清除。
- [x] 以後端 API、Docker 容器及本機 CLI 驗證建立後上傳、上傳失敗重試、容器間隔離及刪除後清理。Focused Docker E2E 已通過；快速 CLI 測試亦確認中斷後會以相同容器授權重試。
