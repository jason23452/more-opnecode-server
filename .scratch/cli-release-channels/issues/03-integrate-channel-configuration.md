# 03: 接通環境設定並完成 CLI 通道整合驗收

Status: resolved

**所屬規格：** CLI prod／dev 發布與下載通道隔離（cli-release-channels）

**What to build:** 開發者與正式環境管理者透過環境設定即可取得各自通道的 CLI。完成本機 dev 設定、Compose 傳遞、設定範例與操作文件，並核對發布流程、API 與安裝腳本之間的整合契約。

**Blocked by:** 01：建立正式版與開發版 CLI 發布流程；02：讓所有 CLI 安裝資訊 API 依 prod／dev 通道選版。

## 驗收條件

- [x] 既有本機後端 `.env` 加入或更新 `OPENCODE_CLI_CHANNEL=dev`，保留其他設定與機密；確認實際 `.env` 未加入版本控制。
- [x] 設定範例說明 prod／dev 對應 tag、預設 prod 與本機 dev 使用方式；Compose 將通道設定傳入後端，未設定時為 prod。
- [x] 清除設定範例與部署設定中可誤導使用者的舊下載 URL 選版方式，文件說明 `OPENCODE_CLI_RELEASE_URL` 不再覆寫通道選版及遷移方法。
- [x] 文件說明兩種 tag 的發布步驟、dev Pre-release、完整平台支援、最新版本判定、最多 60 秒快取延遲及查詢失敗行為。
- [x] 文件說明切換後端通道不會自動替換本機 CLI；須重新取得並執行安裝指令，仍使用既有命令名稱。
- [x] 核對兩個發布流程實際產生的資產名稱與 API 完整性檢查、各平台安裝腳本所需名稱一致，且腳本與執行檔下載固定至同一 tag。
- [x] 驗證從環境設定到 API 安裝指令的完整路徑：dev 僅提供 `cli-dev-*`，prod 與未設定僅提供 `cli-v*`，所有相關 API 都遵循相同規則。
- [x] 驗證 Compose 設定傳遞與正式預設值，並執行本次整合所需的後端、CLI 安裝腳本測試及 workflow 檢查；可沿用有效既有證據，避免無變更時重複檢查。
- [x] 完成針對通道隔離、發布完整性、授權與容器建立失敗副作用的必要整合檢查，修正發現的問題並驗證。
- [x] 交付紀錄區分本機測試／設定檢查與真實 GitHub Actions 執行結果；未經實際執行不得宣稱遠端發布成功，尚未執行的遠端驗證如實列出。

### 驗證紀錄

- 本機：後端 `uv run pytest -q` 為 96 passed、3 skipped；CLI `uv run --with pytest --with trustme --with-editable . pytest tests -q` 為 61 passed、7 subtests passed；Compose 與兩個 workflow 均以 PyYAML `BaseLoader` 成功解析。
- 本機設定檢查：主工作樹既有 `backend/.env` 已安全加入 `OPENCODE_CLI_CHANNEL=dev`，更新時保留其他設定且未輸出內容；已確認 `.env` 仍被 Git 忽略，未納入提交。
- GitHub Actions 與遠端 Release：本次未推送 tag，未執行遠端 workflow 或發布。

## 測試與交付說明

此票驗收聚焦部署設定到安裝來源的跨流程接線，不額外建立前後端 dev 部署環境，也不新增 CLI 自動更新機制。如需 Docker 驗證，遵循專案對主機作業系統及 Windows 原生執行環境的規範。機密值不納入文件、測試輸出或提交。
