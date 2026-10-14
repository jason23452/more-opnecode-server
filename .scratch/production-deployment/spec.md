Status: ready-for-agent

# 前後端正式部署與本機整合驗證

## Problem Statement

目前前端與 FastAPI 後端分別以 npm 與 uv 管理和啟動，專案沒有供兩個服務共同部署的 Docker Compose 設定，也沒有 GitHub Actions 部署流程。維護者必須自行準備部署環境、建置服務並手動保持部署版本一致；同時缺少可在本機驗證兩服務整合啟動的標準方式。

## Solution

提供正式部署 Compose 設定與本機整合驗證 Compose 設定，並為前端及 API 後端提供正式容器映像建置方式。符合 `v*` 的版本 tag 建立時，GitHub Actions 建置前後端映像並發布至 GitHub Container Registry（GHCR），以版本 tag 與 `latest` 標記。映像發布成功後，workflow 使用名稱為 `bojii-system` 且符合 `self-hosted`、`Linux`、`X64`、`more-opencode-server` labels 的 runner 更新既有工作目錄至該 tag、將正式 Compose 設定複製成部署時使用的標準 Compose 檔、拉取 GHCR 最新映像並啟動服務；部署主機不建置映像。

正式部署以前端作為單一服務入口，直接綁定部署主機 `0.0.0.0:3000`。前端 Nginx 將 `/api/` 經 Compose 內部網路轉送至 API 後端；後端不發布 host port。管理 API 可透過公開前端入口到達，管理端點仍以 `OPENCODE_ADMIN_TOKEN` 驗證。部署所需機密由 GitHub Secrets 提供，不提交至 repository。

## User Stories

1. As a 維護者, I want 透過一份正式部署 Compose 設定啟動前端與 API 後端, so that 兩個服務能以一致的版本共同部署。
2. As a 維護者, I want 前端與 API 後端各自有可重複建置並發布至 GHCR 的 production 容器映像, so that 正式環境不需要在部署主機建置或安裝應用程式依賴。
3. As a 維護者, I want 正式 Compose 設定明確描述前端與 API 後端的服務關係, so that 任一服務重建後仍能透過服務名稱互相連線。
4. As a 使用者, I want 從部署主機 `0.0.0.0:3000` 載入前端並經同源 `/api` 呼叫後端, so that 我不必分別連接前端與 API。
5. As a 維護者, I want 前端在正式環境透過 runtime config 使用相對 API 路徑, so that API 可由同一服務入口提供而不需在前端映像中硬編碼部署網域。
6. As a 維護者, I want API 後端在正式環境保有管理 OpenCode 容器所需的同主機 Docker 能力, so that 現有 OpenCode 容器生命週期功能在 Compose 部署後仍可運作。
7. As a 維護者, I want 正式服務所需設定與機密可在部署時注入, so that 不同環境可使用各自的設定且秘密不會進入版本控制。
8. As a 維護者, I want 可在本機以一個 Compose 設定啟動前端與 API 後端, so that 我能在部署前驗證兩服務的整合行為。
9. As a 維護者, I want 本機驗證方式能建置前後端容器映像, so that 驗證結果涵蓋容器建置而不只限於 YAML 語法。
10. As a 維護者, I want 本機驗證確認前端服務入口可回應 HTTP 請求, so that 我能確認前端容器已可服務使用者。
11. As a 維護者, I want 本機驗證確認 API 健康端點可由部署網路存取, so that 我能確認服務間網路與 API 啟動狀態正確。
12. As a 維護者, I want 本機驗證完成後能停止並清理此次建立的服務, so that 驗證不會留下佔用資源的容器。
13. As a 維護者, I want 正式 Compose 設定能在本機被解析驗證, so that 明顯的 Compose 語法或必要設定錯誤能在部署前被發現。
14. As a 維護者, I want push 符合 `v*` 格式的版本 tag 時建置並發布前後端 GHCR 映像，再觸發正式部署, so that 程式碼與部署映像來自同一個發布版本。
15. As a 維護者, I want 部署 workflow 只使用名稱為 `bojii-system` 且符合 runner labels 的 self-hosted runner, so that 部署命令在正式部署主機執行。
16. As a 維護者, I want workflow 將既有 repository 工作目錄更新至觸發部署的 tag, so that 部署內容與發布標籤一致。
17. As a 維護者, I want workflow 在部署主機將 `docker-compose.prod.yaml` 複製成 `docker-compose.yaml`, so that 主機上的 Compose 命令使用該 tag 對應的正式設定。
18. As a 維護者, I want workflow 在 GHCR 映像發布成功後拉取 `latest` 前後端映像並啟動服務, so that tag 部署可完成完整的正式部署，而非只更新檔案。
19. As a 維護者, I want 產生的標準 Compose 檔只存在於部署工作目錄而不自動 commit, so that 部署不會產生自動提交或額外分歧的設定來源。
20. As a 維護者, I want 部署失敗時 workflow 回報失敗狀態, so that 未成功完成的版本不會被誤認為部署成功。
21. As a 維護者, I want 部署 workflow 使用 GitHub Secrets 注入機密, so that 機密值不需要寫入 Compose 檔或 repository。
22. As a 維護者, I want 可以日後設定正式 domain、TLS 與反向代理方式而不改變前後端服務契約, so that 部署入口可配合正式主機環境完成設定。
23. As a 維護者, I want 可用一個明確的本機驗證入口執行 Compose 解析、建置、啟動與 HTTP smoke test, so that 驗證步驟容易重複並能在交付前執行。
24. As a 使用者, I want 容器建立請求可等待 image 建置與 Tunnel 初始化完成, so that 建立流程不會因一般 API 短 timeout 提早中斷。

## Implementation Decisions

- 提供正式部署 Compose 設定 `docker-compose.prod.yaml`，服務範圍只包含前端與 API 後端；服務使用 GHCR 發布的映像，不在正式 Compose 中指定 build context。OpenCode 容器仍由 API 後端依既有領域設計透過同主機 Docker 管理，不作為固定的 Compose 應用服務啟動。
- 正式部署另外提供本機整合驗證 Compose 設定，服務範圍同樣只包含前端與 API 後端；本機設定可提供建置來源、連接埠及驗證所需差異，但服務契約與正式版一致。
- 前端與 API 後端各自提供 production 容器建置方式。前端需保留既有 runtime config 能力，讓 API base URL 可在部署時指向同一服務入口下的相對 `/api` 路徑；API 沿用既有 `/api` 前綴及健康端點。
- 建立 OpenCode 容器的前端 API 請求不使用一般短請求 timeout；前端 Nginx 的 `/api/` upstream read timeout 設為 600 秒，以容納 OpenCode image 首次建置及容器初始化。
- 正式服務入口由前端容器提供，host port 綁定 `0.0.0.0:3000`（可用 `FRONTEND_PORT` 設定 host port）；前端 Nginx 將 `/api/` 代理到 Compose 內部網路中的 `backend:8000`。後端不映射 host port。
- 公開前端入口也會使管理 API 路徑可從該入口到達；後端管理端點使用既有 `OPENCODE_ADMIN_TOKEN` 驗證。遵循 ADR「公開前端入口與容器內部 API 網路」及既有 Tunnel CLI 資料路徑決策。
- API 後端映像需包含 `curl` 與 CA certificates，供後端對 Tunnel URL 執行 HTTPS 健康探測；亦需包含 Docker CLI 與 Buildx CLI plugin，透過部署主機 Docker daemon 建置 OpenCode 容器映像及管理容器。維持既有由同主機 Docker 管理 OpenCode 容器的架構；不得將此應用服務與 OpenCode 容器領域概念混為一談。
- 前後端 GHCR 映像名稱分別為 `ghcr.io/jason23452/more-opnecode-server-frontend` 與 `ghcr.io/jason23452/more-opnecode-server-backend`。每次符合 `v*` 的版本 tag 建置並發布該版本 tag 與 `latest` 兩個 image tag。
- GitHub Actions 使用兩階段工作：GitHub-hosted runner 建置並以 production environment 的 `GHCR_PAT` classic personal access token 發布 GHCR 映像；發布成功後，使用名稱為 `bojii-system`、labels 為 `self-hosted`、`Linux`、`X64`、`more-opencode-server` 的 runner 登入 GHCR 並部署。PAT 至少需具備 `read:packages` 與 `write:packages` scope；存取 private repository package 時另需適當 repository 權限。
- 部署 workflow 確保 `/home/bojii/more-opencode-server` 是目標 repository 工作目錄（若該目錄尚無 Git metadata，先初始化），更新至觸發的 tag 並保留未納入版本控制的部署設定。workflow 將 `docker-compose.prod.yaml` 複製為 `docker-compose.yaml`，登入 GHCR、執行 `docker compose pull`，再以 `docker compose up -d` 啟動服務；正式部署不得執行 `docker compose build`。
- 複製出的 `docker-compose.yaml` 是部署主機工作目錄中的執行產物，不回寫或 commit 至 repository。
- 部署機密由 GitHub production environment secrets 提供：`GHCR_PAT` 用於讀寫 GHCR，`OPENCODE_PASSWORD` 與 `OPENCODE_ADMIN_TOKEN` 用於後端應用設定。部署 workflow 將後端兩項機密保存到部署工作目錄中權限為 `0600`、且不納入版本控制的 `.env`，讓主機後續手動執行 Compose 命令也能載入必要設定。
- 在本機提供單一整合驗證入口，涵蓋本機 Compose 與正式 Compose 設定解析（正式設定解析時使用非機密 throwaway 驗證值）、本機映像建置、服務啟動、前端服務入口 HTTP 回應及 API 健康端點可用性，並清理驗證啟動的服務。
- 遵循既有 ADR「使用 Docker OpenCode 容器與 Cloudflare Quick Tunnel」：本次新增的前後端正式部署不改變 API 後端於同主機 Docker 建立 OpenCode 容器、容器內使用 Cloudflare Quick Tunnel 的既有架構。
- 不新增產品 API 或資料庫；本功能的主要修改範圍為容器建置、Compose 部署描述、本機整合驗證入口及 GitHub Actions 部署流程。

## Testing Decisions

- 好的測試應透過 Docker Compose 的外部可觀察行為驗證服務可解析、建置、啟動及互相連線；不應以 Dockerfile 內部指令順序或 workflow YAML 的文字內容作為主要驗收依據。
- 主要測試 seam 為 Docker Compose 整合邊界。本機驗證入口解析正式與本機 Compose 設定，建置並啟動本機前後端服務，從 HTTP 入口確認前端可用，並確認 API 健康端點可達，結束後清理服務。
- GitHub Actions 的行為驗收以 workflow 執行條件與部署操作為界：確認 `v*` tag 先發布兩個 GHCR 映像，再於符合指定 labels 的 self-hosted runner 更新指定工作目錄、產生部署用標準 Compose 檔、pull 最新映像並啟動；不要求 PR 或一般測試連線至實際 self-hosted 部署主機。
- Workflow 可對非部署分支或非 `v*` tag 的事件做靜態/隔離驗證，確認不會執行正式部署動作。真正部署主機的發佈驗收由 tag workflow 的執行結果確認。
- 前端已有 production build 與 typecheck 指令；後端已有 pytest 測試及 `/api/health` 健康端點。容器驗證應保留這些既有模組層級檢查，Compose smoke test 則覆蓋它們無法驗證的跨容器網路、runtime config、服務入口，以及 backend container 中 curl、Docker CLI 與 Buildx plugin 的可用性。
- 前端容器建立請求測試需確認建立 API 的 Axios timeout 設為無期限、不沿用一般 15 秒 timeout；Nginx `/api/` 設定需允許等待 upstream 最長 600 秒。
- 本機驗證依賴可用 Docker Compose/daemon；CI workflow 部署驗證依賴具備 Docker 權限與指定標籤的 self-hosted runner。測試不得要求 Cloudflare Quick Tunnel 或其外網 URL 才能驗證前後端應用服務整合。

## Out of Scope

- 將 OpenCode 容器改為固定 Compose 服務，或改變 API 後端管理 OpenCode 容器及 Cloudflare Quick Tunnel 的既有生命週期。
- Kubernetes、其他雲端容器平台、GHCR 以外的映像 Registry 或多主機部署。
- 非 tag 發布的自動正式部署、任意 tag 部署或手動審批環節。
- 自動提交部署主機產生的 `docker-compose.yaml` 回 repository。
- 在本規格中決定正式 domain、TLS 憑證、額外外部反向代理設定或 GitHub Secrets 的具體值；正式前端入口直接發布 host port 3000。
- 建立資料庫、遷移資料或改動前後端產品功能/API 契約。
- 在本機整合驗證中啟動 OpenCode 容器或 Cloudflare Quick Tunnel。

## Further Notes

- 本功能起始時專案沒有前端或 API 後端的應用程式 Dockerfile、部署 workflow 或 Compose 設定；原有 Dockerfile 僅用於 API 管理的 OpenCode 執行環境。
- 前端 runtime config 可在靜態網站啟動時提供或替換，部署時無需為 API URL 重新執行前端 build；應使用此既有能力支援單一服務入口。
- 後端健康端點為 `/api/health`。正式部署的 API 健康檢查及本機 smoke test 應以實際服務可達性為準。
- self-hosted runner 需要對指定 repository 工作目錄及 Docker daemon 有操作權限，且 production environment 的 `GHCR_PAT` 必須能讀寫對應 GHCR packages。部署設定須避免將必要環境設定提交至 Git，並避免 tag checkout 清理掉主機本地機密設定。
- 正式 domain、TLS、外部反向代理仍待維護者提供；GitHub production environment secrets 的名稱已定義，但其正式值由維護者設定。
- 規格狀態為 `ready-for-agent`，依 issue tracker 慣例發布於本功能目錄。
