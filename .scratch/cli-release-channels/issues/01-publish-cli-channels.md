# 01: 建立正式版與開發版 CLI 發布流程

Status: resolved

**所屬規格：** CLI prod／dev 發布與下載通道隔離（cli-release-channels）

**What to build:** 維護者推送 `cli-v*` 或 `cli-dev-*` tag 後，GitHub Actions 分別產生可供安裝的正式版或開發版 CLI。所有支援平台通過測試與建置後，才完成含執行檔及安裝腳本的 Release 發布。

**Blocked by:** 無，可立即開始。

## 驗收條件

- [x] 保留 `cli-v*` 正式版流程，新增只由 `cli-dev-*` tag 推送觸發的開發版流程；兩者不觸發對方流程，dev 分支推送不觸發開發版發布。
- [x] 兩通道皆建置 Windows x64、macOS x64、macOS arm64、Linux x64，沿用現有資產名稱與安裝方式。
- [x] 建置流程執行既有 CLI 測試，並以各平台獨立執行檔的 `--help` 驗證可執行性。
- [x] Release 對應原始觸發 tag；四個執行檔與 PowerShell、shell 安裝腳本全部備妥後才完成發布，失敗或上傳中的版本不會以完整可用版本呈現。
- [x] `cli-dev-*` 發布為 Pre-release 且明確不成為正式 Latest；`cli-v*` 發布為正式 Release。
- [x] 檢查 workflow 語法、tag 篩選、建置到發布的依賴、完整資產清單，以及 Pre-release／Latest 設定。
- [x] 提供兩種 tag 的發布方式與預期資產說明，記錄實際完成的驗證；尚未執行的 GitHub Actions 明確標示尚未執行。

### 驗證紀錄

- `uv run --project cli --with pytest pytest cli/tests -q`：61 passed，7 subtests passed。
- 以 PyYAML `BaseLoader` 解析 `.github/workflows/cli-release.yml` 與 `.github/workflows/cli-dev-release.yml`：皆成功。
- `git diff --check`：通過。
- 已檢查兩份 workflow 的 tag 篩選、四平台矩陣、CLI 測試與 `--help` 步驟、publish 對 build 的依賴、六項資產、draft 發布及通道專屬 Pre-release／Latest 設定。
- GitHub Actions 尚未執行；本票未推送 tag，未建立或發布遠端 Release。

## 測試與交付說明

此票可獨立驗證發布契約，不依賴後端選版功能。不得以本機 workflow 檢查宣稱已完成 GitHub 遠端發布；實際 tag 推送與發布需另外取得操作授權。
