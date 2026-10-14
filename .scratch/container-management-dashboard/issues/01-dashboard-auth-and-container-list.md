# 01: Dashboard 路由式分頁、驗證與容器清單

**What to build:** 內部管理者進入 Dashboard 後可透過以多個 React Router 路由為基礎的分頁，在容器清單等主要功能頁之間導覽；可輸入管理 token、查看受管理的 OpenCode 容器清單及其健康狀態，並手動更新清單。頁面涵蓋載入、空清單、API 錯誤及管理 token 無效等狀態，且提供其餘 Dashboard 操作可沿用的頁面整合測試接縫。

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] `/` 首頁呈現 OpenCode 容器管理 Dashboard。
- [x] Dashboard 主要分頁各自對應已註冊的 React Router 路由；切換分頁會更新 URL，且瀏覽器上一頁/下一頁可返回先前分頁，不以僅更新元件內部狀態的 tab 實作取代路由。
- [x] 至少提供容器清單與建立容器兩個主要路由分頁；各分頁可直接透過其 URL 進入，重新整理後仍會落在對應分頁。
- [x] 管理者可輸入管理 token；token 僅保留在目前頁面的執行期狀態，不寫入瀏覽器儲存空間或 URL。
- [x] 帶有 `Authorization: Bearer <管理 token>` 的清單請求可顯示容器識別碼、Tunnel URL 與「健康／異常」狀態。
- [x] 提供手動重新整理；清單載入、空清單及非 401 錯誤均有明確的使用者可見狀態。
- [x] 401 顯示管理 token 無效的提示並保留輸入值，讓管理者可修正後重試。
- [x] 建立可在頁面層操作 Dashboard、攔截管理 API HTTP 請求/回應並驗證可見行為的前端整合測試接縫；必要時加入最小測試工具。
- [x] 頁面測試驗證各分頁路由可直達、分頁導覽與瀏覽器歷史行為，以及 token 不持久化、Bearer header、清單呈現、手動重新整理、空/載入/錯誤狀態及 401 修正重試；不依賴 Docker 或 Cloudflare Quick Tunnel。

## Answer

已整合至 `integration/container-management-dashboard`；前端頁面測試、型別檢查與 production build 均通過。
