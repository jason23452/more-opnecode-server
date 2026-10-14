# 01: 建立前後端容器映像與本機整合驗證

**What to build:** 維護者可在本機建置並共同啟動前端與 API 後端，透過 HTTP 確認前端服務入口與 API 健康端點可用，並在驗證完成後清理服務；這也提供正式部署可重用的 production 容器映像。

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] 前端與 API 後端皆可建置為 production 容器映像，並以容器啟動正式應用程式。
- [ ] 本機整合驗證可使用一個 Compose 操作建置並啟動前端與 API 後端，不需啟動 OpenCode 容器或 Cloudflare Quick Tunnel。
- [ ] 驗證可透過 HTTP 確認前端服務入口回應，並確認 API `/api/health` 健康端點可達。
- [ ] 驗證完成或失敗時都會停止並清理本次建立的服務。
- [ ] 本機整合驗證可重複執行，且不依賴正式環境機密。
- [ ] 前端容器保留 runtime config 能力，讓 API base URL 可由啟動時設定。
