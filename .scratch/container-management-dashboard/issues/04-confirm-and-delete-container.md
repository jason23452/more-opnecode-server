# 04: 確認並刪除容器

**What to build:** 管理者可安全地從 Dashboard 移除不再使用的 OpenCode 容器；操作前清楚得知容器及其容器工作資料都會永久移除，取消確認不會影響容器。

**Blocked by:** 01: Dashboard 路由式分頁、驗證與容器清單.

**Status:** resolved

- [x] 每個容器提供刪除操作，送出 DELETE 前顯示明確的確認步驟。
- [x] 確認文案指出刪除會強制停止並移除容器，且永久清除容器工作資料。
- [x] 管理者取消確認時不送出刪除請求，清單維持不變。
- [x] 確認後使用目前頁面的 Bearer 管理 token 呼叫既有 DELETE API；請求期間避免重複送出。
- [x] 刪除成功後從清單移除該容器，並提供成功結果；失敗時保留容器並顯示錯誤。
- [x] 401 沿用管理 token 無效提示及保留輸入值行為。
- [x] 頁面整合測試驗證確認/取消、DELETE 請求與 Bearer header、成功後清單更新及錯誤狀態；不依賴真實 Docker。

## Answer

已整合至 `integration/container-management-dashboard`；刪除確認/取消、Bearer 驗證、清單更新與錯誤處理測試均通過，型別檢查與 production build 均通過。
