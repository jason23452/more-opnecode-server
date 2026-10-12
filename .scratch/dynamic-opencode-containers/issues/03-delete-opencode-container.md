# 03: 完整刪除 OpenCode 容器

**What to build:** 讓內部管理者刪除不再需要的 OpenCode 容器，並完整釋放其執行環境、Tunnel 與暫存工作資料。

**Blocked by:** 01: 建立並公開 OpenCode 容器.

**Status:** resolved

- [x] 刪除 API 可依容器識別碼停止並移除 OpenCode 容器。
- [x] 刪除操作會終止該容器的 `cloudflared` Tunnel。
- [x] 刪除操作會清除該容器專屬的暫存工作資料。
- [x] 刪除完成後，該容器不再出現在列表或單筆查詢的有效資源中，且不再能透過原 Tunnel URL 連線。
- [x] 以真實 Docker 容器、Cloudflare Tunnel 與 API 驗證完整清理；刪除 API 受內部管理存取控制。
