Status: ready-for-agent

# 前後端正式部署與本機整合驗證

## Problem Statement

目前前端與 FastAPI 後端分別以 npm 與 uv 管理和啟動，專案沒有供兩個服務共同部署的 Docker Compose 設定，也沒有 GitHub Actions 部署流程。維護者必須自行準備部署環境、建置服務並手動保持部署版本一致；同時缺少可在本機驗證兩服務整合啟動的標準方式。

## Solution

提供正式部署 Compose 設定與本機整合驗證 Compose 設定，並為前端及 API 後端提供正式容器映像建置方式。新增 GitHub Actions，在符合 `v*` 的版本 tag 建立時，使用標籤為 `bojii-system` 的 self-hosted runner，更新既有工作目錄至該 tag、將正式 Compose 設定複製成部署時使用的標準 Compose 檔，並建置及啟動服務。

正式部署由單一服務入口提供前端與 API 存取。部署所需機密由 GitHub Secrets 提供，不提交至 repository。domain、TLS、反向代理細節及 Secrets 名稱和值在本規格中保留為部署設定，不預設其具體值。

## User Stories

1. As a 維護者, I want 透過一份正式部署 Compose 設定啟動前端與 API 後端, so that 兩個服務能以一致的版本共同部署。
2. As a 維護者, I want 前端與 API 後端各自有可重複建置的 production 容器映像, so that 正式環境不需要在容器啟動時安裝開發工具或依賴。
3. As a 維護者, I want 正式 Compose 設定明確描述前端與 API 後端的服務關係, so that 任一服務重建後仍能透過服務名稱互相連線。
4. As a 使用者, I want 從單一服務入口載入前端並呼叫 API, so that 我不必分別記住前端與 API 的公開位置。
5. As a 維護者, I want 前端在正式環境透過 runtime config 使用相對 API 路徑, so that API 可由同一服務入口提供而不需在前端映像中硬編碼部署網域。
6. As a 維護者, I want API 後端在正式環境保有管理 OpenCode 容器所需的同主機 Docker 能力, so that 現有 OpenCode 容器生命週期功能在 Compose 部署後仍可運作。
7. As a 維護者, I want 正式服務所需設定與機密可在部署時注入, so that 不同環境可使用各自的設定且秘密不會進入版本控制。
8. As a 維護者, I want 可在本機以一個 Compose 設定啟動前端與 API 後端, so that 我能在部署前驗證兩服務的整合行為。
9. As a 維護者, I want 本機驗證方式能建置前後端容器映像, so that 驗證結果涵蓋容器建置而不只限於 YAML 語法。
10. As a 維護者, I want 本機驗證確認前端服務入口可回應 HTTP 請求, so that 我能確認前端容器已可服務使用者。
11. As a 維護者, I want 本機驗證確認 API 健康端點可由部署網路存取, so that 我能確認服務間網路與 API 啟動狀態正確。
12. As a 維護者, I want 本機驗證完成後能停止並清理此次建立的服務, so that 驗證不會留下佔用資源的容器。
13. As a 維護者, I want 正式 Compose 設定能在本機被解析驗證, so that 明顯的 Compose 語法或必要設定錯誤能在部署前被發現。
14. As a 維護者, I want push 符合 `v*` 格式的版本 tag 時觸發正式部署, so that 部署版本由明確發布標籤控制。
15. As a 維護者, I want 部署 workflow 只使用標籤為 `bojii-system` 的 self-hosted runner, so that 部署命令在正式部署主機執行。
16. As a 維護者, I want workflow 將既有 repository 工作目錄更新至觸發部署的 tag, so that 部署內容與發布標籤一致。
17. As a 維護者, I want workflow 在部署主機將正式 Compose 設定複製成標準部署檔名, so that 主機上的 Compose 命令使用該 tag 對應的正式設定。
18. As a 維護者, I want workflow 在更新及複製設定後建置並啟動服務, so that tag 部署可完成完整的正式部署，而非只更新檔案。
19. As a 維護者, I want 產生的標準 Compose 檔只存在於部署工作目錄而不自動 commit, so that 部署不會產生自動提交或額外分歧的設定來源。
20. As a 維護者, I want 部署失敗時 workflow 回報失敗狀態, so that 未成功完成的版本不會被誤認為部署成功。
21. As a 維護者, I want 部署 workflow 使用 GitHub Secrets 注入機密, so that 機密值不需要寫入 Compose 檔或 repository。
22. As a 維護者, I want 可以日後設定正式 domain、TLS 與反向代理方式而不改變前後端服務契約, so that 部署入口可配合正式主機環境完成設定。
23. As a 維護者, I want 可用一個明確的本機驗證入口執行 Compose 解析、建置、啟動與 HTTP smoke test, so that 驗證步驟容易重複並能在交付前執行。

## Implementation Decisions

- 提供正式部署 Compose 設定，服務範圍只包含前端與 API 後端；OpenCode 容器仍由 API 後端依既有領域設計透過同主機 Docker 管理，不作為固定的 Compose 應用服務啟動。
- 正式部署另外提供本機整合驗證 Compose 設定，服務範圍同樣只包含前端與 API 後端；本機設定可提供建置來源、連接埠及驗證所需差異，但服務契約與正式版一致。
- 前端與 API 後端各自提供 production 容器建置方式。前端需保留既有 runtime config 能力，讓 API base URL 可在部署時指向同一服務入口下的相對 `/api` 路徑；API 沿用既有 `/api` 前綴及健康端點。
- Compose 的正式服務拓撲以單一對外服務入口呈現前端及 API。對外入口實際如何透過反向代理/TLS/domain 實現，以及使用哪些公開連接埠，尚待維護者提供部署環境設定。
- API 後端必須能呼叫部署主機 Docker daemon，維持既有由同主機 Docker 管理 OpenCode 容器的架構。不得將此應用服務與 OpenCode 容器領域概念混為一談。
- GitHub Actions 以 `v*` tag 作為部署觸發條件，並限制部署工作在標籤 `bojii-system` 的 self-hosted runner 上執行。
- 部署 workflow 更新 `/home/bojii/more-opencode-server` 既有 repository 工作目錄至觸發的 tag；更新方式需保留部署所需但不納入版本控制的環境設定。workflow 將正式 Compose 設定複製為 `docker-compose.yaml`，然後執行服務建置與背景啟動。
- 複製出的 `docker-compose.yaml` 是部署主機工作目錄中的執行產物，不回寫或 commit 至 repository。
- 部署機密由 GitHub Secrets 提供；Secrets 的名稱、必要值清單及注入方式需配合維護者稍後提供的部署配置定義。規格不假設任何具體憑證值。
- 在本機提供單一整合驗證入口，涵蓋本機 Compose 與正式 Compose 設定解析、本機映像建置、服務啟動、前端服務入口 HTTP 回應及 API 健康端點可用性，並清理驗證啟動的服務。
- 遵循既有 ADR「使用 Docker OpenCode 容器與 Cloudflare Quick Tunnel」：本次新增的前後端正式部署不改變 API 後端於同主機 Docker 建立 OpenCode 容器、容器內使用 Cloudflare Quick Tunnel 的既有架構。
- 不新增產品 API 或資料庫；本功能的主要修改範圍為容器建置、Compose 部署描述、本機整合驗證入口及 GitHub Actions 部署流程。

## Testing Decisions

- 好的測試應透過 Docker Compose 的外部可觀察行為驗證服務可解析、建置、啟動及互相連線；不應以 Dockerfile 內部指令順序或 workflow YAML 的文字內容作為主要驗收依據。
- 主要測試 seam 為 Docker Compose 整合邊界。本機驗證入口解析正式與本機 Compose 設定，建置並啟動本機前後端服務，從 HTTP 入口確認前端可用，並確認 API 健康端點可達，結束後清理服務。
- GitHub Actions 的行為驗收以 workflow 執行條件與部署操作為界：確認 `v*` tag 會選中 `bojii-system` runner，使用觸發 tag 更新指定工作目錄、產生部署用標準 Compose 檔，並執行建置/啟動命令；不要求 PR 或一般測試連線至實際 self-hosted 部署主機。
- Workflow 可對非部署分支或非 `v*` tag 的事件做靜態/隔離驗證，確認不會執行正式部署動作。真正部署主機的發佈驗收由 tag workflow 的執行結果確認。
- 前端已有 production build 與 typecheck 指令；後端已有 pytest 測試及 `/api/health` 健康端點。容器驗證應保留這些既有模組層級檢查，Compose smoke test 則覆蓋它們無法驗證的跨容器網路、runtime config 與服務入口行為。
- 本機驗證依賴可用 Docker Compose/daemon；CI workflow 部署驗證依賴具備 Docker 權限與指定標籤的 self-hosted runner。測試不得要求 Cloudflare Quick Tunnel 或其外網 URL 才能驗證前後端應用服務整合。

## Out of Scope

- 將 OpenCode 容器改為固定 Compose 服務，或改變 API 後端管理 OpenCode 容器及 Cloudflare Quick Tunnel 的既有生命週期。
- Kubernetes、雲端容器平台、映像 Registry 發佈流程或多主機部署。
- 非 tag 發布的自動正式部署、任意 tag 部署或手動審批環節。
- 自動提交部署主機產生的 `docker-compose.yaml` 回 repository。
- 在本規格中決定正式 domain、TLS 憑證、反向代理產品/設定、公開 port 或 GitHub Secrets 的具體名稱與值。
- 建立資料庫、遷移資料或改動前後端產品功能/API 契約。
- 在本機整合驗證中啟動 OpenCode 容器或 Cloudflare Quick Tunnel。

## Further Notes

- 目前專案沒有前端或 API 後端的應用程式 Dockerfile，也沒有 GitHub Actions workflow 或 Compose 設定；現有 Dockerfile 用於 API 管理的 OpenCode 執行環境。
- 前端 runtime config 可在靜態網站啟動時提供或替換，部署時無需為 API URL 重新執行前端 build；應使用此既有能力支援單一服務入口。
- 後端健康端點為 `/api/health`。正式部署的 API 健康檢查及本機 smoke test 應以實際服務可達性為準。
- self-hosted runner 需要對指定 repository 工作目錄及 Docker daemon 有操作權限；部署設定須避免將必要環境設定提交至 Git，並避免 tag checkout 清理掉主機本地機密設定。
- Domain、TLS、反向代理與 GitHub Secrets 參數待維護者補充後，於實作時確認正式 Compose 的環境變數/設定介面。
- 規格狀態為 `ready-for-agent`，依 issue tracker 慣例發布於本功能目錄。
