# 03: 以版本 tag 自動部署正式服務

**What to build:** 維護者 push 符合 `v*` 的版本 tag 後，GitHub Actions 建置前後端容器映像並發布至 GHCR，以版本 tag 與 `latest` 標記。映像發布成功後，正式部署主機更新至該 tag 的程式版本，將 `docker-compose.prod.yaml` 複製成標準 Compose 檔，pull 最新 package images 並啟動服務；部署主機不建置映像，產生的 Compose 檔不回寫 repository。

**Blocked by:** 02: 建立前後端正式部署 Compose 與單一服務入口.

**Status:** resolved

- [x] 只有符合 `v*` 的 tag 會觸發 workflow；GitHub-hosted job 建置並發布前後端 images 至 GHCR，分別附上版本 tag 與 `latest`。
- [x] 發布 images 成功後，部署 job 限定使用名稱為 `bojii-system`、labels 為 `self-hosted`、`Linux`、`X64`、`more-opencode-server` 的 runner，並以 production environment 的 `GHCR_PAT` 登入 GHCR 拉取 images。
- [x] Workflow 將 `/home/bojii/more-opencode-server` 既有 repository 工作目錄更新至觸發部署的 tag，並保留未納入版本控制的部署設定。
- [x] Workflow 在部署工作目錄將 `docker-compose.prod.yaml` 複製為 `docker-compose.yaml`，不自動 commit 或 push 該產生檔案。
- [x] Workflow 執行 `docker compose pull` 並在背景啟動前端與 API 後端服務；部署主機不執行 image build。
- [x] Workflow 由 GitHub Secrets 注入正式部署機密，且不將機密值寫入版本控制或輸出至日誌。
- [x] 任一更新、複製、建置或啟動步驟失敗時，workflow 以失敗狀態結束。

**Validation:** 部署腳本臨時 Git remote/fake Docker 行為測試 2 passed，驗證選擇 tag、複製設定、保留主機設定、執行 `compose pull`/`up` 且失敗能傳遞。尚未 push `v*` tag 驗證實際 GHCR publish/deploy；GitHub production environment 需設定 `GHCR_PAT`、`OPENCODE_PASSWORD` 與 `OPENCODE_ADMIN_TOKEN` Secrets。
