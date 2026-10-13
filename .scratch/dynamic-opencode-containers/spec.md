Status: ready-for-agent

# 動態 OpenCode 容器與 Cloudflare Tunnel

## Problem Statement

使用者目前無法透過後端 API 動態取得一個已準備好的 OpenCode 執行環境，也沒有可持續確認及恢復其 Cloudflare Tunnel 的管理能力。手動建立環境、確認 OpenCode 服務可連線、處理 Tunnel 中斷及清理資源都需要額外操作；Tunnel URL 改變時，呼叫者也無法可靠取得最新網址。使用者也無法從本機將 project folder 傳入遠端容器，或透過本機終端互動操作容器內的 OpenCode TUI。目前專案檔案會先經管理後端再寫入容器，讓檔案資料佔用後端的網路與記憶體資源。

## Solution

提供一組僅供內部管理者使用的後端 API，建立、列出、查詢及刪除固定規格的 OpenCode 容器。建立 API 等待容器內 OpenCode 服務與 Cloudflare Quick Tunnel 就緒後，回傳容器識別碼及 Tunnel URL。服務透過 `4096` port 對外提供；Tunnel 由容器內的 `cloudflared` 建立。

後端持續透過 Tunnel URL 健康探測 OpenCode 服務，必要時自動重建 Tunnel 並更新 URL。若復原失敗，保留容器並回報故障狀態。部署設定提供 OpenCode 共用密碼與資源/監控限制。驗證以實際 Docker、後端 API、Cloudflare Quick Tunnel 及外部 HTTP 探測進行黑箱整合測試。

建立容器後，內網管理 API 提供該容器專屬的 CLI 上傳與連線資訊。使用者在本機執行獨立安裝的專案 CLI，將指定資料夾直接經該容器的 Cloudflare Tunnel 傳入容器工作目錄，並透過本機終端經同一 Tunnel 連入容器內的 OpenCode TUI；CLI 的上傳與 TUI 連線不呼叫管理後端，也不需要連線至 `localhost:8000`。管理者以多次單容器 API 呼叫建立多台互相隔離的 OpenCode 執行環境。管理後端只負責容器生命週期及管理資訊，不轉送專案檔案或 TUI 終端資料。

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
27. As an 內部管理者, I want 建立容器後取得該容器專屬的 CLI 上傳與連線資訊, so that 我能從本機將專案送入容器並進入其 OpenCode TUI。
28. As an OpenCode 使用者, I want 使用本機專案 CLI 指定一個 project folder 並上傳至指定容器, so that 我不需要在本機安裝或執行 OpenCode。
29. As an OpenCode 使用者, I want 上傳成功後透過本機終端互動使用容器內的 OpenCode TUI, so that 開發工作實際由遠端 OpenCode 執行。
30. As an OpenCode 使用者, I want 可分別執行上傳與連線，也可一次上傳後直接連線, so that 我能重試傳輸或稍後重新連入同一容器。
31. As an OpenCode 使用者, I want 上傳中斷時保留容器並可重試, so that 暫時性傳輸問題不會使已建立的遠端環境遺失。
32. As an OpenCode 使用者, I want 每台容器取得互相隔離的專案副本, so that 多台遠端 OpenCode 可各自執行工作而不共用工作目錄。
33. As an OpenCode 使用者, I want 每個容器同時只允許一個互動式 TUI 連線, so that 多個終端不會同時控制同一個互動工作階段。
34. As an OpenCode 使用者, I want 專案檔案由本機 CLI 直接經容器 Tunnel 傳送, so that 大型檔案資料不必經管理後端中繼。
35. As an OpenCode 使用者, I want 專案上傳與 TUI 連線都只使用容器 Tunnel, so that 本機 CLI 不需要連線至管理後端。
36. As an 內部管理者, I want Tunnel URL 改變後可透過內網管理 API 取得最新 upload/connect URL, so that 我能重新提供有效的 CLI 命令。
37. As an OpenCode 使用者, I want 大型專案分塊傳送並在所有區塊驗證完成後才更新工作目錄, so that Tunnel 單次請求大小限制不會阻止上傳或造成半套專案。
38. As an OpenCode 使用者, I want 遠端 TUI 使用本機終端的實際欄數與列數並在視窗調整時更新, so that TUI 版面能完整顯示且不把終端控制回覆當成 prompt 文字。

## Implementation Decisions

- 採用單一領域功能管理 OpenCode 容器及其 Tunnel 生命週期；API 需支援建立、列出、單筆查詢與刪除。管理 API 是內網控制面，不由 Tunnel 對外公開，也不承載專案檔案或 TUI 終端資料。具體路徑、HTTP 方法及回應欄位由實作者依現有 FastAPI 慣例定義。
- 後端在部署所在主機的 Docker 建立固定規格的 OpenCode 容器。容器包含 curl、Python、uv、Node.js、npm、pnpm、OpenCode SDK，以及執行 Tunnel 所需的 `cloudflared`。
- 容器內的 Tunnel ingress 固定透過 `4096` port 對外提供；Ingress 將一般 OpenCode HTTP 請求轉送至 OpenCode server，並將專案上傳路徑轉送至容器內的上傳接收器。`cloudflared` 將 Cloudflare Quick Tunnel 轉送至此 ingress。
- 建立 API 等待 OpenCode 服務與 Tunnel 通過健康檢查後才回覆成功。初始化逾時、時間上限與其他監控門檻均應可由部署設定調整；具體預設值由實作階段決定。失敗時清理未就緒的容器與其暫存工作資料。
- 容器健康狀態以透過當前 Tunnel URL 對根路徑 `/` 發出 HTTP 探測判定；探測使用部署設定的 OpenCode 密碼，以成功 HTTP 回應作為健康條件。需區分健康與故障，並以連續失敗門檻觸發 Tunnel 重建。
- Tunnel 重建後更新容器目前的 Tunnel URL。呼叫端透過列表或單筆查詢取得最新 URL，不新增 webhook 或推播通知。
- Tunnel 多次無法恢復時保留 OpenCode 容器及工作資料，並透過查詢結果呈現故障狀態；後續仍可繼續嘗試恢復。
- 刪除容器須停止並移除 Docker 容器、終止 Tunnel，並清除該容器的暫存工作資料。
- 後端重新啟動後，Docker 中既有容器應持續執行；後端重新盤點既有容器，恢復狀態管理及健康監控。
- OpenCode 服務採用部署設定提供的共用密碼。管理 API 僅供內部管理者使用，不提供使用者層級容器所有權隔離；管理 API 的憑證或網路保護方式須由部署設定提供。
- 管理者仍逐台呼叫 `POST /api/opencode/containers` 建立容器。成功回應除容器識別碼與 Tunnel URL 外，另提供該容器專屬的 CLI 上傳與連線資訊；上傳 URL 指向該容器的 Tunnel ingress。專屬憑證不得要求使用者在本機持有 Docker 權限或 OpenCode 管理密碼。
- 提供獨立安裝於使用者本機的專案 CLI。CLI 接收使用者指定的 project folder，預設排除常見大型產物目錄，將其上傳至指定容器；CLI 亦提供分開的上傳與連線操作，以及先上傳再連線的一鍵操作。
- CLI 以 GitHub Releases 預建獨立執行檔發佈；支援 Windows x64、macOS Intel/Apple Silicon 與 Linux x64。容器建立回應提供 PowerShell、macOS、Linux 各自的下載安裝命令；使用者不需安裝 Python、uv 或 Node.js。
- 專案檔案資料由本機 CLI 直接透過該容器的 Cloudflare Tunnel 傳至容器內上傳接收器；FastAPI 管理後端不接收、不緩衝、不轉送專案 payload。每個容器擁有隔離的專案副本；不進行本機與遠端的持續雙向同步，也不建立 Git worktree/branch 流程。
- 容器上傳接收器以容器專屬 upload token 驗證 CLI，只能寫入該容器的專案工作目錄。上傳採分塊傳輸；未收到並驗證完整專案前保留既有工作目錄，完成後才以安全的 staging/atomic replacement 更新。重送相同區塊需可安全重試。
- Tunnel URL 可能在建立後或傳輸期間改變。管理者可透過內網管理 API 查詢最新 upload/connect URL，並以先前建立回應中的容器專屬 token 重新執行 CLI 命令；CLI 不呼叫管理後端刷新 URL。因 Quick Tunnel URL 會變動，不承諾使用者端自動取得新 URL。
- 專案資料隨容器存續；移除容器時一併清除，不要求獨立持久化 Docker volume。CLI 只有在全部區塊完成且專案安裝成功後，才可連入該容器的 OpenCode TUI。
- 本機 CLI 經 Tunnel ingress 連入容器內的互動式 OpenCode TUI；容器端 relay 配置 PTY，每個容器同時僅允許一個 TUI 工作階段。FastAPI 管理後端不執行 Docker exec 來中繼 TUI。
- CLI 將本機終端初始尺寸與後續 resize 事件作為獨立 WebSocket 控制訊息傳給容器 relay；relay 對 PTY 設定視窗列/欄數並通知 OpenCode TUI 重排版。尺寸控制訊息不得混入鍵盤輸入或顯示為 prompt 文字。
- 執行環境相容性：Docker Desktop 可在 Windows 上運行，而 WSL 可刻意不安裝 Linux Docker CLI 且不啟用 WSL Integration。後端在 WSL 中若偵測到 `docker.exe`，所有管理 Docker 呼叫須自動使用它；build 的 WSL 絕對路徑須轉成 Docker Desktop 可解析的 Windows 路徑。Tunnel ingress 與容器內接收器處理 upload/TUI 資料流；原生 Linux 環境沿用 `docker`。
- 以部署設定限制單一容器 CPU、記憶體及同時執行容器數量。
- 遵循 ADR「使用 Docker OpenCode 容器與 Cloudflare Quick Tunnel」及 ADR「專案檔案經 Tunnel 直接上傳」：使用同主機 Docker、容器內 `cloudflared` 與臨時 Quick Tunnel；接受 URL 可因 Tunnel 重建而改變，並以健康監控及控制 API 查詢最新 upload URL 因應。
- 主要測試 seam 為實際運作環境中的黑箱 HTTP 管理 API 與本機 CLI 可觀察的上傳/終端互動。測試需啟動真實後端及 Docker 環境，透過 API 建立實際容器與 Quick Tunnel，並從 Tunnel URL 驗證服務可達及管理生命週期。

## Testing Decisions

- 好的測試應從呼叫者可見的 HTTP 回應、Tunnel URL 可達性、容器生命週期與健康狀態轉換驗證行為，不依賴內部類別、方法或未承諾的資料儲存細節。
- 主要驗收測試使用真實 Docker daemon、實際 OpenCode 容器與 Cloudflare Quick Tunnel：呼叫建立 API，使用配置的 OpenCode 密碼確認成功回應的 Tunnel URL 可透過外部 HTTP 連線至 OpenCode `4096` 服務；再呼叫列表、單筆查詢與刪除 API，確認狀態及資源清理結果。
- 上傳驗收需驗證 CLI 可指定本機資料夾、套用預設排除規則，並確認專案 payload 直接通過目標容器 Tunnel ingress，而非送至管理後端。確認不同容器的專案副本互相隔離，且刪除容器會清除其工作資料。
- 分塊上傳驗收需驗證區塊可重試、缺少/損壞區塊不會更新目前工作目錄，全部區塊驗證完成後才安裝專案；測試資料需超過單次 HTTP 請求大小限制。
- Tunnel URL 變更驗收需使舊 URL 失效，確認管理者可透過內網管理 API 查詢新 upload/connect URL，並以原容器 token 手動重新執行 CLI；確認 CLI 未連線至管理 API，檔案區塊與 TUI 流量仍直接經 Tunnel。
- 終端連線驗收需確認 CLI 使用 Tunnel URL 而非管理 API URL 進入遠端 OpenCode TUI；上傳完成前不能開始互動，同一容器第二個 TUI 連線受限，並驗證中斷後需手動取得新 URL 才能重新連線。
- TUI 尺寸驗收需從已知本機終端尺寸建立連線，確認遠端 PTY/TUI 使用相同欄數與列數；調整本機終端尺寸後確認遠端收到 resize 並重排版，Windows Terminal 的終端查詢回覆不可出現在 prompt。
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
- 透過 Cloudflare Tunnel 對外提供內網管理 API；Tunnel 僅公開單一容器自己的 OpenCode、專案上傳與 TUI ingress。
- 由管理後端代理或緩衝專案檔案 payload；僅由後端處理控制資訊與建立/管理容器。
- 本機 OpenCode 執行、雙向即時檔案同步、跨容器共用工作目錄、Git worktree/branch 管理及自動合併。
- 超過復原重試後自動刪除故障容器。

## Further Notes

- OpenCode SDK 的確切套件名稱/版本、OpenCode 服務啟動方式、API 路徑與 schema、管理 API 的具體驗證機制，以及資源與監控設定預設值尚未在對話中定義，應於實作設計時選定並記錄。
- Tunnel URL 改變時，CLI 不透過 `localhost` 或其他管理 API 自動刷新；管理者需先從內網管理 API 取得新 URL，再以現有容器 token 重新執行 CLI 命令。
- Tunnel 直接上傳仍受 Cloudflare Quick Tunnel 與容器 ingress 的單次請求大小限制；實作需以分塊傳輸避免單一請求超限，並提供清楚的區塊校驗與錯誤回報。
- Cloudflare Quick Tunnel URL 可能在建立或復原時改變；呼叫端應以查詢 API 回傳的目前 Tunnel URL 為準。
- 規格狀態為 `ready-for-agent`，依 issue tracker 慣例發布於本功能目錄。
