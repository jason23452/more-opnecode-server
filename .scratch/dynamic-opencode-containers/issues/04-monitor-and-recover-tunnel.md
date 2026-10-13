# 04: 監控並自動復原 Tunnel

**What to build:** 當 OpenCode 容器的 Tunnel URL 中斷時，自動重建 Tunnel、更新 URL，並讓管理者得知目前健康或故障狀態，同時保留容器工作。

**Blocked by:**
- 01: 建立並公開 OpenCode 容器.
- 02: 列出、查詢並重新盤點 OpenCode 容器.

**Status:** resolved

- [x] 後端依部署設定的週期，透過目前 Tunnel URL 的根路徑 `/` 發送 HTTP 健康探測，並使用 OpenCode 部署密碼完成探測。
- [x] 探測週期、連續失敗門檻與重試策略可由部署設定調整；單次失敗不會立即觸發 Tunnel 重建。
- [x] 達到連續失敗門檻時，後端自動重建 Cloudflare Quick Tunnel，並將 Tunnel 導向既有 OpenCode `4096` 服務。
- [x] Cloudflare Quick Tunnel 建立回覆 429 或程序意外結束時，容器 supervisor 依可配置指數退避重試，直到 Tunnel 恢復或容器被刪除。
- [x] Tunnel 重建成功後更新目前 Tunnel URL；列表及單筆查詢回傳新 URL，且新 URL 可外部連線至同一 OpenCode 容器。
- [x] Tunnel 多次重建仍失敗時，保留 OpenCode 容器及其工作資料，並讓列表與單筆查詢呈現故障狀態。
- [x] 後端重新啟動後，既有容器的 Tunnel 健康監控可恢復。
- [x] 以真實 Docker 與 Cloudflare Quick Tunnel 驗證中斷、重建、新 URL 可用、故障狀態及容器工作資料保留。
