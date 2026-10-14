# 03: 以版本 tag 自動部署正式服務

**What to build:** 維護者 push 符合 `v*` 的版本 tag 後，正式部署主機會更新至該 tag 的程式版本，使用正式 Compose 設定建置並啟動服務；部署產生的標準 Compose 檔留在主機，不回寫 repository。

**Blocked by:** 02: 建立前後端正式部署 Compose 與單一服務入口.

**Status:** resolved

- [x] 只有符合 `v*` 的 tag 會觸發正式部署，部署 job 限定使用 `bojii-system` self-hosted runner。
- [x] Workflow 將 `/home/bojii/more-opencode-server` 既有 repository 工作目錄更新至觸發部署的 tag，並保留未納入版本控制的部署設定。
- [x] Workflow 在部署工作目錄將正式 Compose 設定複製為 `docker-compose.yaml`，不自動 commit 或 push 該產生檔案。
- [x] Workflow 使用部署設定建置並在背景啟動前端與 API 後端服務。
- [x] Workflow 由 GitHub Secrets 注入正式部署機密，且不將機密值寫入版本控制或輸出至日誌。
- [x] 任一更新、複製、建置或啟動步驟失敗時，workflow 以失敗狀態結束。

**Validation:** 部署腳本的臨時 Git remote/fake Docker 行為測試 2 passed；shell syntax、Compose YAML parse 與 `git diff --check` 通過。未對正式部署主機執行 tag deploy；GitHub production environment 需設定 `OPENCODE_PASSWORD` 與 `OPENCODE_ADMIN_TOKEN` Secrets。
