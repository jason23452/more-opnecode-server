# CLI prod／dev 發布通道實作 Session

## 摘要與目標

完成 `.scratch/cli-release-channels/spec.md` 所列的正式版／開發版 CLI 發布與下載隔離，整合所有三張 ticket 至單一整合分支，完成必要測試、風險導向 review 及驗收清單更新。

本輪在 2026-10-16 13:06:48 CST 開始，使用者指定 1 小時時限，目標截止 14:06:48 CST。

## 背景與需求

- `cli-v*` 是正式版 tag，後端 `prod` 僅選取此通道的正式 Release。
- `cli-dev-*` 是開發版 tag，後端 `dev` 僅選取此通道的開發 Pre-release。
- 本機後端 `.env` 設為 dev；正式環境預設 prod；所有提供 CLI 安裝資訊的 API 必須共用隔離的選版方式。
- repo 原先沒有 `dev` 分支；使用者要求先從 `master` 開啟本地 `dev`，並以一小時完成。

## 決策與理由

- 建立 `dev` 自 `master`（起始 commit `881fd72`），依 repo 規範以 `spec/cli-release-channels` 作為整合分支並建立獨立 worktree。
- Ticket 01（workflow）與 02（selector/API）沒有相互依賴，平行實作；Ticket 03（設定/文件/整合）等待前兩者合併後執行。
- GitHub Releases 由 tag 觸發；開發版用 draft 先備妥六項資產後才公開，設為 Pre-release 並明確不成為正式 Latest。
- `.env` 含本機機密，不讀出或提交其內容；以安全腳本只更新 `OPENCODE_CLI_CHANNEL=dev`，確認 `.env` 仍被 Git 忽略。
- 未推送 tag，未執行遠端 GitHub Actions 或發布 Release；本機 workflow/YAML 驗證不能代替遠端驗證。

## 已完成工作與變更檔案

- 建立分支 `dev` 及整合分支/worktree `spec/cli-release-channels`。
- Ticket 01：新增開發版 workflow、調整正式版發布的 draft/資產完整性處理、workflow 契約測試與 CLI 發布文件。
- Ticket 02：新增 `OPENCODE_CLI_CHANNEL` 設定及 `CliReleaseSelector`；兩個 API 安裝入口共用 Release 選版、完整資產與發布時間篩選、GitHub 分頁、每通道快取、逾時/錯誤處理；移除舊自訂 URL 的覆寫能力。
- Ticket 03：Compose 通道傳遞、設定範例及操作遷移文件、部署契約測試；本機 `backend/.env` 已安全更新為 dev。
- 三張 ticket 均更新 checklist 並標為 `resolved`。
- 變更涉及 `.github/workflows/`、`backend/src/App/`、`backend/src/Features/Opencode/`、後端測試、`cli/README.md`、workflow 測試、Compose、`.scratch/cli-release-channels/issues/`。
- 整合分支最後提交 `4743390`（驗收清單與實際 `.env` 驗證紀錄）。

## 驗證結果

- 後端：`uv run pytest -q` → 96 passed、3 skipped。
- CLI：`uv run --with pytest --with trustme --with-editable . pytest tests -q` → 61 passed、7 subtests passed。第一次全套執行有一個既有 WSS 測試 timeout；單獨重跑通過，之後完整重跑全部通過。
- Compose 及兩份 release workflow 以 PyYAML `BaseLoader` 解析成功；`git diff --check` 通過。
- 本機 `.env` 安全檢查確認只有一筆 `OPENCODE_CLI_CHANNEL=dev`，檔案仍被 Git 忽略；其餘 `.env` 內容未輸出。
- Standards review：未發現明確標準違反；記錄兩份 workflow 重複建置步驟為低度 Duplicated Code heuristic，考量流程需獨立觸發及各自 Release 設定，未抽象共用。
- Spec review：指出本機 `.env` 尚未設定（已在原工作樹安全完成，並更新 ticket 證據）；另質疑 pagination 停止條件。核對 `CliReleases.py` 的行為為每頁剛好 100 筆即繼續，僅在少於 100 筆時結束；跨頁測試亦證明第二頁選出版本，故此項為誤讀，不需程式修正。
- 遠端 GitHub Actions 及真實 Release 尚未驗證。

## 未決問題／風險

- GitHub Release 尚未真實執行。須由維護者依文件推送一個正式或開發 tag 後確認 Actions 工作流程、Release 類型及六項資產。
- 本機已安裝 CLI 不會自動更新或依後端通道替換；重新取得並執行 API 提供的安裝指令即可切換/更新。
- 使用者同意後，整合分支已於 2026-10-16 合併至本地 `dev`（fast-forward 至 `59e3b9d`）；本次建立的三個 ticket worktrees、integration worktree 及相應 branches 已確認乾淨並清理。

## 下一步（依優先順序）

1. 維護者之後推送正式或開發 tag，確認 GitHub Actions、Release 類型與六項資產，完成尚未執行的遠端發布驗證。
2. 本輪程式、測試及文件已合併至本地 `dev`；若需要同步遠端，依維護者的 Git 發布流程另行處理。

## 相關參照

- 規格：`.scratch/cli-release-channels/spec.md`
- Tickets：`.scratch/cli-release-channels/issues/01-publish-cli-channels.md`、`02-select-cli-channel-in-apis.md`、`03-integrate-channel-configuration.md`
- 最終整合分支：`dev`（`spec/cli-release-channels` 已合併並清理）
- Commits：`77a8ece`（Ticket 01）、`15c57ee`（Ticket 02）、`3f0c84f`（Ticket 03）、`4743390`（驗收與 checklist）
- 主 session 可取得的 implementer sessions：`ses_ebce46028ffeFK2nSLD05fKSEF`（01）、`ses_ebce46009ffeeV6gcbN6m60P1M`（02）、`ses_ebcd17f9cffe6fq4viYVYw3X2w`（03）。Merger sessions：`ses_ebcd664cdffeAnywnNh88LDItL`（01）、`ses_ebcd45135ffecVvFCXP58hmRqc`（02）、`ses_ebcc9ae7affetquk07pMFpJxCD`（03）。Review sessions：`ses_ebcc600c4ffeWXVEAswYLu8ydj`、`ses_ebcc600a6ffer32gp7kStsyjpA`（第一次錯誤工作目錄）、`ses_ebcc5270affewJYeON3pxde3hi`、`ses_ebcc526d3ffealzRwagcj47XPe`（有效 review）。
- 本機 OpenCode `storage/session` 不存在，且以可用路徑搜尋未找到上述 session 對話記錄；本筆記整合主 session 可見的 subagent 最終回覆及其以檔案、commit、測試驗證的結果，未將無法讀取的內文當作已整理。
