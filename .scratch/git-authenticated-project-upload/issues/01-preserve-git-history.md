# 01: 上傳時保留 Git 專案歷史

**What to build:** 使用者上傳 Git 專案後，遠端 OpenCode 容器保有原本的分支、提交歷史與 remote，讓 agent 能在既有版本脈絡中工作；一般非 Git 專案上傳仍可使用。

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Git 專案上傳後，遠端工作目錄保留 `.git` 中的分支、提交歷史與 remote 設定。
- [x] 專案封裝不包含 Git 認證憑證；remote URL 中可能存在的敏感認證資訊不會在上傳輸出中揭露。
- [x] 非 Git 專案仍可上傳，既有依賴、建置產物與快取目錄排除行為維持有效。
- [x] 小型與分塊上傳均可安裝含 Git 歷史的專案，並遵守既有封裝大小與安全檢查。
- [x] CLI 上傳測試與容器上傳接收器測試驗證遠端可讀取 Git 歷史且不會從封裝取得認證。
