# 02: 建立前後端正式部署 Compose 與單一服務入口

**What to build:** 維護者可使用正式 Compose 啟動前端與 API 後端，映像從 GHCR 拉取而不在部署主機建置；使用者可由 `0.0.0.0:3000` 存取前端，並由前端 Nginx 經容器內部網路 proxy `/api/` 至後端。正式 Compose 使用 `docker-compose.prod.yaml`，後端不發布 host port，且仍能透過部署主機 Docker 管理 OpenCode 容器。

**Blocked by:** 01: 建立前後端容器映像與本機整合驗證.

**Status:** resolved

- [x] 正式 Compose 使用 GHCR 前端與 API 後端映像，不包含 `build` 設定，且可在部署主機 pull 後啟動服務。
- [x] 前端以 `0.0.0.0:3000` 提供單一服務入口，並以 runtime config 使用同源相對 `/api` 路徑；前端 Nginx 經 Compose 內部網路代理至 backend。
- [x] API 後端映像包含 Docker CLI 與 Buildx plugin，可透過同主機 Docker daemon 建置 OpenCode 容器映像及管理容器。
- [x] 正式服務所需機密與環境設定由部署環境提供，不需提交機密至 repository；必要憑證未設定時 Compose 會拒絕解析。
- [x] 正式 Compose 可在未提供真實機密值的本機情境下以 throwaway 驗證值解析，且正式 Compose 檔名為 `docker-compose.prod.yaml`。
- [x] 正式 Compose 不將 OpenCode 容器或 Cloudflare Quick Tunnel 定義為固定的應用服務。
- [x] 前端 host port 綁定 `0.0.0.0:3000`，API 後端只在 Compose 內部網路提供服務、不映射 host port。
- [x] 管理 API 透過公開前端入口可達，管理端點仍要求 `OPENCODE_ADMIN_TOKEN`。

**Validation:** Windows Docker Compose build/up 驗證前端 `0.0.0.0:3000` 可達、`/api/health` 經 frontend Nginx 回傳 200，且未帶 Bearer token 的管理端點回傳 401；backend 僅在 Compose network 暴露 `8000/tcp`，沒有 host port mapping。backend container 內 `docker buildx version` 成功，並以 `docker build` 實際建立 OpenCode image。
