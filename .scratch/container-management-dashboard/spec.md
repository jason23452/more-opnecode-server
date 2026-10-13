Status: ready-for-agent

# OpenCode 容器管理 Dashboard

## Problem Statement

內部管理者目前雖可透過後端管理 API 建立及管理 OpenCode 容器，前端卻沒有可操作的管理介面。管理者必須自行呼叫 API、整理容器健康狀態與 Tunnel URL，並從回應中找出連線及上傳資訊；這使建立、連線及清理容器的流程不便且容易出錯。

## Solution

將目前的 `/` 首頁改為 OpenCode 容器管理 Dashboard，直接串接既有管理 API。Dashboard 的主要功能以多個 React Router 路由分頁呈現，至少提供容器清單與建立容器分頁；切換分頁會更新 URL，支援直接進入及瀏覽器歷史導覽。管理者可輸入管理 token、查看及手動更新 OpenCode 容器清單、建立容器、開啟容器連線 URL、依作業系統取得 CLI 連線指令，以及在明確確認後刪除容器。介面呈現容器健康狀態、載入/錯誤/空清單等必要狀態，並在建立成功後提供完整建立資訊。

## User Stories

1. As an 內部管理者, I want 在首頁看到 OpenCode 容器管理 Dashboard, so that 我能從單一介面管理容器。
2. As an 內部管理者, I want 透過多個路由式分頁導覽 Dashboard 的主要功能, so that 每個功能都能直接連結並支援瀏覽器上一頁/下一頁。
3. As an 內部管理者, I want 在 Dashboard 輸入管理 token, so that 前端能以管理者身分呼叫受保護的管理 API。
4. As an 內部管理者, I want 管理 token 只保留在目前頁面的記憶體中, so that 重新整理或關閉頁面後不會繼續保存憑證。
5. As an 內部管理者, I want 在尚未輸入管理 token 時看到輸入提示, so that 我知道需要先完成管理 API 驗證才能管理容器。
6. As an 內部管理者, I want 輸入管理 token 後載入受管理的 OpenCode 容器清單, so that 我能掌握目前已建立的環境。
7. As an 內部管理者, I want 在清單中看到每個容器的識別碼、容器健康狀態與目前 Tunnel URL, so that 我能辨認並檢查每個環境。
8. As an 內部管理者, I want 以「健康／異常」查看容器健康狀態, so that 狀態表達 OpenCode 服務與 Tunnel URL 的可用性，而非只表示 Docker 程序是否存活。
9. As an 內部管理者, I want 手動重新整理容器清單, so that 我能取得最新 Tunnel URL 及健康狀態。
10. As an 內部管理者, I want 在沒有受管理容器時看到空清單提示及建立入口, so that 我能開始建立第一個環境。
11. As an 內部管理者, I want 從 Dashboard 建立 OpenCode 容器, so that 我不必直接呼叫管理 API。
12. As an 內部管理者, I want 建立容器期間看到進行中狀態並避免重複送出, so that 建立作業完成前不會意外建立多個環境。
13. As an 內部管理者, I want 建立成功後立即看到容器識別碼、Tunnel URL、上傳/連線 URL、token 及 CLI 安裝/操作命令, so that 我能直接開始連線或上傳專案。
14. As an 內部管理者, I want 複製建立回應中的 URL、token 與命令, so that 我能在需要的工具中使用對應資訊。
15. As an OpenCode 使用者, I want 從容器清單開啟容器連線 URL, so that 我能在新分頁連到該容器的遠端 TUI 工作階段。
16. As an OpenCode 使用者, I want 在容器詳細資訊中選擇 macOS、Windows 或 Linux, so that 我能取得符合本機作業系統的連線指令。
17. As an OpenCode 使用者, I want 複製所選平台的容器連線指令, so that 我能在本機 CLI 使用該容器的連線資訊。
18. As an 內部管理者, I want API 回應 401 時看到管理 token 無效的提示且欄位保留, so that 我能修正 token 並重試。
19. As an 內部管理者, I want 在管理 API 發生其他錯誤時看到可理解的失敗訊息, so that 我能判斷操作是否成功並採取後續行動。
20. As an 內部管理者, I want 刪除容器前看到確認提示, so that 我不會因誤觸而移除環境。
21. As an 內部管理者, I want 刪除確認明確說明容器及其容器工作資料都會永久移除, so that 我能在了解資料影響後做出決定。
22. As an 內部管理者, I want 確認刪除後看到操作進行中及結果, so that 我能知道容器是否已成功移除。
23. As an 內部管理者, I want 刪除成功後從清單移除該容器, so that Dashboard 狀態反映最新管理結果。
24. As an 內部管理者, I want 建立、清單、單筆查詢及刪除都使用同一個目前頁面管理 token, so that 所有管理操作都符合管理 API 的驗證要求。

## Implementation Decisions

- 前端以容器管理 Dashboard 取代目前 `/` 首頁的起始介紹畫面。Dashboard 的主要功能以多個 React Router 路由分頁呈現，至少包含容器清單及建立容器；分頁導覽更新 URL，支援直接進入、重新整理與瀏覽器歷史導覽。
- 新介面屬於 OpenCode 容器功能；容器 API 型別、管理 API 呼叫與 Dashboard 互動留在該功能內，共用 API client 和 runtime API base URL 設定沿用現有 Shared 能力。
- 管理 API 呼叫需以 `Authorization: Bearer <管理 token>` 傳送管理 token。Token 由使用者在 Dashboard 輸入，只保留在目前頁面的執行期狀態，不寫入 localStorage、sessionStorage 或 URL。重新整理或關閉頁面後需重新輸入。
- 只串接既有後端 API，不變更後端契約：
  - `GET /opencode/containers` 取得容器清單；回應含 `id`、`status`（`healthy` 或 `unhealthy`）、`url`、`upload_url`、`connect_url`。
  - `POST /opencode/containers` 建立容器，無 request body；成功回應含 `id`、URL、upload/connect token、平台安裝命令及 upload/connect 命令。
  - `GET /opencode/containers/{container_id}?environment={mac|windows|linux}` 取得指定容器的平台專屬命令；依作業系統提供 `upload_command` 與 `connect_command`。
  - `DELETE /opencode/containers/{container_id}` 刪除受管理容器，成功時回應 `204`。
- 管理 API 路徑以前端既有 runtime API base URL 為基底；管理 API 保持為內網控制面。容器連線與專案上傳仍直接經由容器 Tunnel ingress，不經由管理 API 中繼。
- 「開啟容器」代表以清單提供的 `connect_url` 開新分頁，不表示透過管理 API 啟動或重啟 Docker 容器。提供平台選擇及單筆查詢以取得可複製的 CLI 連線指令。
- 建立成功回應中提供的完整資訊呈現於建立結果；可複製 URL、token 與命令。清單本身不應假設含有建立時的 token；平台命令透過單筆查詢取得。
- 清單於取得 token 後載入，使用者可手動重新整理；不進行定時自動輪詢。
- `healthy` / `unhealthy` 以「健康／異常」等可理解狀態呈現，不標示為 Docker「執行中／已停止」。
- DELETE 前顯示確認步驟，指出刪除會強制停止並移除容器，且永久清除容器工作資料。取消確認不送出 DELETE。
- 401 錯誤明確提示管理 token 無效，保留輸入值以便修改和重試；其他 API 錯誤提供操作失敗訊息。建立、重新整理、指令查詢及刪除需各自反映載入、成功或錯誤狀態，並避免重複送出進行中的操作。
- 遵循既有領域詞彙：OpenCode 容器、Tunnel URL、Tunnel ingress、容器健康狀態、容器工作資料、容器連線 URL、容器連線指令與管理 token。管理 token 不等同容器連線 token。
- 遵循 ADR「使用 Docker OpenCode 容器與 Cloudflare Quick Tunnel」及「內網管理後端與 Tunnel 用戶端資料路徑分離」：管理 API 用於內網管理；外部連線使用容器 Tunnel ingress；Tunnel URL 可能改變，管理者可透過重新查詢取得最新資訊。

## Testing Decisions

- 好的測試以管理者可觀察的 Dashboard 行為、呈現狀態及實際發出的 HTTP 請求為驗收依據；不耦合 React 元件內部 state、Hook、元件階層或實作細節。
- 使用者已確認以單一最高層前端頁面整合接縫驗證：在瀏覽器/頁面層操作 Dashboard，攔截管理 API 的 HTTP 請求與回應，檢查畫面和請求行為。若缺少必要工具，新增最小前端測試工具與執行指令。
- 頁面測試覆蓋路由分頁直達、分頁導覽/瀏覽器歷史、token 不持久化、Bearer header、清單載入與手動重新整理、healthy/unhealthy 呈現、空清單、建立成功與完整結果、平台命令查詢、URL 開新分頁、複製操作、刪除確認及取消/確認、成功後清單更新、401 token 修正重試、其他錯誤及操作進行中狀態。
- 測試不得依賴真實 Docker daemon、Cloudflare Quick Tunnel 或外部網路；後端契約由既有後端 API 測試負責，前端使用受控 HTTP 回應驗證串接行為。
- Prior art：目前前端沒有測試 runner、test script 或既有測試檔；後端既有測試使用 FastAPI `TestClient` 驗證外部 HTTP 行為。本功能需建立前端頁面整合測試的最小測試基礎。

## Out of Scope

- 修改或新增後端 API、容器生命週期、Tunnel、管理 token 驗證機制或資料持久化。
- 使用者登入、角色/權限管理、帳號或容器所有權隔離。
- 儲存管理 token 至瀏覽器儲存空間或提供跨工作階段記住 token 功能。
- 自動定時輪詢、狀態推播或 Tunnel URL 變更通知。
- 暫停、停止、啟動或重啟既有容器；既有 API 僅支援建立、查詢及刪除，刪除會停止並移除容器。
- 以 Docker 程序存活狀態取代 API 提供的容器健康狀態。
- 透過管理 API 中繼專案檔案或 TUI 終端流量。
- 管理容器內專案檔案、同步、Git worktree/branch 或跨容器工作資料。
- 更改目前前端 API base URL/runtime config 部署方式。

## Further Notes

- 現有後端管理 API 需要 Bearer 管理 token；前端不可把 token 硬編碼至程式或部署設定。
- 清單 API 提供容器健康狀態，不提供獨立 Docker running/stopped 欄位；介面狀態須依健康狀態呈現。
- 建立容器成功後才會回傳新容器的連線與上傳資訊；若使用者離開頁面且未另行保存，需重新透過受保護 API 查詢可取得的命令資訊。
- 本規格發布於本機 Markdown issue tracker，狀態為 `ready-for-agent`。
