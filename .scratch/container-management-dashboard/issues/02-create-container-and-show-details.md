# 02: 建立容器並呈現建立資訊

**What to build:** 管理者可從 Dashboard 建立 OpenCode 容器，並在建立完成後立即查看及複製新容器的連線與上傳資訊，接著回到清單確認該環境。

**Blocked by:** 01: Dashboard 路由式分頁、驗證與容器清單.

**Status:** resolved

- [x] 使用目前頁面的管理 token 呼叫既有建立 API；建立期間顯示進行中狀態並避免重複送出。
- [x] 建立容器操作位於 Dashboard 的建立容器路由分頁；直接進入該路由時仍呈現建立介面。
- [x] 建立成功後呈現容器識別碼、Tunnel URL、upload/connect URL、upload/connect token、各平台 CLI 安裝命令及 upload/connect 命令。
- [x] 建立結果中的 URL、token 及命令均可個別複製，並提供可辨識的複製結果回饋。
- [x] 建立失敗時顯示明確錯誤，不錯誤地呈現成功結果；401 沿用 token 無效提示及保留輸入值行為。
- [x] 建立成功後清單更新並顯示新容器。
- [x] 頁面整合測試驗證建立請求的 Bearer header、進行中/成功/失敗行為、建立資訊呈現與複製操作；不依賴真實 Docker 或 Tunnel。

## Answer

已整合至 `integration/container-management-dashboard`；建立流程及頁面整合測試通過，型別檢查與 production build 均通過。
