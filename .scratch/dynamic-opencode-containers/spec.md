Status: ready-for-agent

# 動態 OpenCode 容器與 Cloudflare Tunnel

## Problem Statement

使用者目前無法透過後端 API 動態取得一個已準備好的 OpenCode 執行環境，也沒有可持續確認及恢復其 Cloudflare Tunnel 的管理能力。手動建立環境、確認 OpenCode 服務可連線、處理 Tunnel 中斷及清理資源都需要額外操作；Tunnel URL 改變時，呼叫者也無法可靠取得最新網址。

## Solution

提供一組僅供內部管理者使用的後端 API，建立、列出、查詢及刪除固定規格的 OpenCode 容器。建立 API 等待容器內 OpenCode 服務與 Cloudflare Quick Tunnel 就緒後，回傳容器識別碼及 Tunnel URL。服務透過 `4096` port 對外提供；Tunnel 由容器內的 `cloudflared` 建立。

後端持續透過 Tunnel URL 健康探測 OpenCode 服務，必要時自動重建 Tunnel 並更新 URL。若復原失敗，保留容器並回報故障狀態。部署設定提供 OpenCode 共用密碼與資源/監控限制。驗證以實際 Docker、後端 API、Cloudflare Quick Tunnel 及外部 HTTP 探測進行黑箱整合測試。

## User Stories

1. As an 內部管理者, I want 透過一個 API 建立 OpenCode 容器, so that 我不必手動準備執行環境。
2. As an 內部管理者, I want 建立 API 只在 OpenCode 與 Tunnel 都就緒後成功回應, so that 我拿到的 Tunnel URL 可立即使用。
3. As an 內部管理者, I want 建立成功時取得容器識別碼與 Tunnel URL, so that 我能連線並管理該 OpenCode 容器。
4. As an 內部管理者, I want 初始化超過設定期限時收到明確失敗回應, so that 建立請求不會無限等待。
5. As an 內部管理者, I want 初始化失敗時未就緒的容器與暫存工作資料能自動清理, so that 失敗請求不留下孤兒資源。
6. As an OpenCode 使用者, I want 容器預先提供 curl、Python、uv、Node.js、npm、pnpm 與 OpenCode SDK, so that 我能在一致的開發環境中工作。
7. As an OpenCode 使用者, I want OpenCode 服務固定透過容器內 `4096` port 提供, so that Tunnel 能以一致方式轉送請求。
8. As an OpenCode 使用者, I want 每個 OpenCode 容器都有自己的暫存工作資料, so that 不同容器的工作檔案互相隔離。
9. As an OpenCode 使用者, I want OpenCode 服務使用部署設定的密碼, so that 公開可連線的 Tunnel URL 不代表未經驗證即可使用服務。
10. As an 內部管理者, I want OpenCode 密碼不出現在建立 API 回應中, so that API 回應不會洩露服務憑證。
11. As an 內部管理者, I want 列出所有受管理的 OpenCode 容器及其狀態與目前 Tunnel URL, so that 我能檢視目前執行中的環境。
12. As an 內部管理者, I want 依容器識別碼查詢單一容器, so that 我能檢查該容器目前是否健康及取得最新 Tunnel URL。
13. As an 內部管理者, I want Tunnel URL 改變後查詢 API 回傳最新網址, so that 呼叫端不會持續使用已失效的網址。
14. As an 內部管理者, I want 健康監控透過 Tunnel URL 的根路徑 `/` 探測 OpenCode 服務, so that 健康狀態反映外部實際連線能力。
15. As an 內部管理者, I want 健康檢查採週期性探測且支援連續失敗門檻, so that 單次網路抖動不會造成不必要的 Tunnel 重建。
16. As an 內部管理者, I want Tunnel 故障時系統自動重建 Tunnel, so that 短暫或可恢復的連線問題不需要人工介入。
17. As an OpenCode 使用者, I want Tunnel 重建成功後取得新的 Tunnel URL 並可連線至同一 OpenCode 服務, so that Tunnel 復原不會遺失容器中的工作。
18. As an 內部管理者, I want 多次 Tunnel 重建仍失敗時容器保留並標示故障, so that 我可以檢查及診斷問題，而不會遺失工作資料。
19. As an 內部管理者, I want 刪除操作停止並移除容器、終止 Tunnel 並清除容器工作資料, so that 不再使用的環境能完整釋放。
20. As an 內部管理者, I want 後端重新啟動後既有 OpenCode 容器仍能被盤點與管理, so that 後端程序重啟不會使執行環境失聯。
21. As an 內部管理者, I want 後端重啟後恢復容器狀態與 Tunnel 健康監控, so that 既有環境仍能自動復原。
22. As a 系統管理者, I want 設定單一容器的 CPU 與記憶體上限, so that 單一容器不會耗盡主機資源。
23. As a 系統管理者, I want 設定同時執行容器數量上限, so that 建立請求不會使主機承載超出容量。
24. As a 系統管理者, I want 設定初始化逾時、健康探測週期、連續失敗門檻與重試策略, so that 我能依部署環境調整容錯與資源使用。
25. As an 內部管理者, I want 建立、列表、查詢與刪除 API 僅供可信任內部管理者呼叫, so that 未授權呼叫者不能建立或控制容器。
26. As a 維護者, I want 透過真實 Docker 與 Cloudflare Tunnel 執行整合驗證, so that 我能確認 API 建立的環境能在實際部署依賴下成功運作。

## Implementation Decisions

- 採用單一領域功能管理 OpenCode 容器及其 Tunnel 生命週期；API 需支援建立、列出、單筆查詢與刪除。具體路徑、HTTP 方法及回應欄位由實作者依現有 FastAPI 慣例定義。
- 後端在部署所在主機的 Docker 建立固定規格的 OpenCode 容器。容器包含 curl、Python、uv、Node.js、npm、pnpm、OpenCode SDK，以及執行 Tunnel 所需的 `cloudflared`。
- 容器啟動 OpenCode 服務並監聽 `4096` port。每個容器內執行 `cloudflared`，使用 Cloudflare Quick Tunnel 產生臨時 Tunnel URL，將外部請求轉送至該服務。
- 建立 API 等待 OpenCode 服務與 Tunnel 通過健康檢查後才回覆成功。初始化逾時、時間上限與其他監控門檻均應可由部署設定調整；具體預設值由實作階段決定。失敗時清理未就緒的容器與其暫存工作資料。
- 容器健康狀態以透過當前 Tunnel URL 對根路徑 `/` 發出 HTTP 探測判定；探測使用部署設定的 OpenCode 密碼，以成功 HTTP 回應作為健康條件。需區分健康與故障，並以連續失敗門檻觸發 Tunnel 重建。
- Tunnel 重建後更新容器目前的 Tunnel URL。呼叫端透過列表或單筆查詢取得最新 URL，不新增 webhook 或推播通知。
- Tunnel 多次無法恢復時保留 OpenCode 容器及工作資料，並透過查詢結果呈現故障狀態；後續仍可繼續嘗試恢復。
- 刪除容器須停止並移除 Docker 容器、終止 Tunnel，並清除該容器的暫存工作資料。
- 後端重新啟動後，Docker 中既有容器應持續執行；後端重新盤點既有容器，恢復狀態管理及健康監控。
- OpenCode 服務採用部署設定提供的共用密碼。管理 API 僅供內部管理者使用，不提供使用者層級容器所有權隔離；管理 API 的憑證或網路保護方式須由部署設定提供。
- 以部署設定限制單一容器 CPU、記憶體及同時執行容器數量。
- 遵循 ADR「使用 Docker OpenCode 容器與 Cloudflare Quick Tunnel」：使用同主機 Docker、容器內 `cloudflared` 與臨時 Quick Tunnel；接受 URL 可因 Tunnel 重建而改變，並以健康監控及查詢最新 URL 因應。
- 主要測試 seam 為實際運作環境中的黑箱 HTTP 管理 API。測試需啟動真實後端及 Docker 環境，透過 API 建立實際容器與 Quick Tunnel，並從 Tunnel URL 驗證服務可達及管理生命週期。

## Testing Decisions

- 好的測試應從呼叫者可見的 HTTP 回應、Tunnel URL 可達性、容器生命週期與健康狀態轉換驗證行為，不依賴內部類別、方法或未承諾的資料儲存細節。
- 主要驗收測試使用真實 Docker daemon、實際 OpenCode 容器與 Cloudflare Quick Tunnel：呼叫建立 API，使用配置的 OpenCode 密碼確認成功回應的 Tunnel URL 可透過外部 HTTP 連線至 OpenCode `4096` 服務；再呼叫列表、單筆查詢與刪除 API，確認狀態及資源清理結果。
- Tunnel 復原測試需在測試容器中使目前 Tunnel 失效，確認健康監控會重建 Tunnel、產生可用的新 URL、查詢 API 回傳新 URL，並確認 OpenCode 容器與工作狀態仍保留。多次復原失敗時，確認容器保留且 API 呈現故障狀態。
- 驗證初始化逾時、資源數量上限、CPU/記憶體設定、未授權管理呼叫及刪除後暫存資料清除等外部行為。
- 執行上述整合測試需有可用 Docker daemon、容器建置能力、外網連線及 Cloudflare Quick Tunnel 可用性；測試不得依賴固定 URL，應以每次建立或重建實際回傳的 URL 驗證。
- 現有 prior art 是後端以 FastAPI `TestClient` 呼叫健康 API，並檢查 HTTP 狀態、回應內容與 request ID。此功能需新增 Docker/Cloudflare 實際環境的 API 整合測試；目前程式庫沒有既有容器或 Tunnel 測試可沿用。

## Out of Scope

- 使用 Kubernetes、遠端 Docker 主機或其他雲端容器平台管理執行環境。
- Cloudflare 固定自訂網域、命名 Tunnel 或保證 Tunnel URL 固定不變。
- 容器工具、映像、啟動命令或服務埠由 API 呼叫者自訂。
- 使用者層級帳號、容器所有權隔離或面向公眾的容器管理 API。
- URL 變更 webhook、推播或事件通知。
- 停止後保留容器的暫停功能；刪除即完整清除容器、Tunnel 與工作資料。
- 超過復原重試後自動刪除故障容器。

## Further Notes

- OpenCode SDK 的確切套件名稱/版本、OpenCode 服務啟動方式、API 路徑與 schema、管理 API 的具體驗證機制，以及資源與監控設定預設值尚未在對話中定義，應於實作設計時選定並記錄。
- Cloudflare Quick Tunnel URL 可能在建立或復原時改變；呼叫端應以查詢 API 回傳的目前 Tunnel URL 為準。
- 規格狀態為 `ready-for-agent`，依 issue tracker 慣例發布於本功能目錄。
