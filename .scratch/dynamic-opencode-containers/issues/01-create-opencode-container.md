# 01: 建立並公開 OpenCode 容器

**What to build:** 讓內部管理者透過建立 API 取得已就緒的 OpenCode 容器及可連線的 Cloudflare Tunnel URL。

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] 後端可在同主機 Docker 建立固定規格的 OpenCode 容器，包含 curl、Python、uv、Node.js、npm、pnpm、OpenCode SDK 與 `cloudflared`。
- [ ] 容器啟動 OpenCode 服務並監聽 `4096` port；使用容器內的 `cloudflared` 建立 Cloudflare Quick Tunnel，產生臨時 Tunnel URL。
- [ ] 內部管理者呼叫建立 API 後，API 等待 OpenCode 及 Tunnel 就緒，成功時回傳容器識別碼與可使用的 Tunnel URL。
- [ ] OpenCode 服務使用部署設定的共用密碼；管理 API 受到內部管理者可用的憑證或網路邊界保護，且 API 不回傳 OpenCode 密碼。
- [ ] 初始化逾時或失敗時，API 回報失敗並清理未就緒容器及其暫存工作資料。
- [ ] CPU、記憶體、同時執行容器數量及初始化逾時可由部署設定限制；超出容器數量上限時不建立新容器。
- [ ] 以真實 Docker、後端 API 及 Cloudflare Quick Tunnel 驗證建立流程，並使用配置密碼確認回傳的 URL 可連至 OpenCode `4096` 服務。
