# 02: 列出、查詢並重新盤點 OpenCode 容器

**What to build:** 讓內部管理者查看所有 OpenCode 容器或單一容器的狀態與目前 Tunnel URL；後端重啟後仍能重新接手既有容器。

**Blocked by:** 01: 建立並公開 OpenCode 容器.

**Status:** resolved

- [x] 列表 API 回傳受管理容器的識別碼、健康狀態及目前 Tunnel URL。
- [x] 單筆查詢 API 依容器識別碼回傳該容器狀態與目前 Tunnel URL。
- [x] 後端重新啟動後，既有 Docker 容器仍持續執行，並重新出現在列表及單筆查詢結果中。
- [x] 後端重新啟動後恢復既有容器的狀態管理，列表及單筆查詢持續回傳其最新 Tunnel URL。
- [x] 以真實 Docker 容器及 API 驗證列表、單筆查詢，以及重啟後的重新盤點；所有管理操作均受內部管理存取控制。
