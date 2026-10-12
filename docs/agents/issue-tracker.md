# Issue 追蹤方式：本機 Markdown

本儲存庫的 issue 與規格以 Markdown 檔案記錄於 `.scratch/`。

## 慣例

- 每個功能使用一個目錄：`.scratch/<feature-slug>/`
- 規格放在 `.scratch/<feature-slug>/spec.md`
- 實作票據各自存為 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，從 `01` 開始編號，不將多張票據合併在同一檔案
- 每張 issue 檔案上方以 `Status:` 記錄 triage 狀態（角色名稱參見 `triage-labels.md`）
- 留言與討論歷程附加於檔案末尾的 `## Comments` 標題下

## 技能要求「發布至 issue tracker」時

在 `.scratch/<feature-slug>/` 下建立檔案；必要時一併建立目錄。

## 技能要求「取得相關票據」時

讀取使用者指定路徑的檔案；使用者通常會直接提供路徑或票號。

## Wayfinding 慣例

供 `/wayfinder` 使用。map 是一份檔案，每張票據則各有一份子檔案。

- **Map**：`.scratch/<effort>/map.md`，記錄 Notes、Decisions-so-far 與 Fog。
- **子票據**：`.scratch/<effort>/issues/NN-<slug>.md`，從 `01` 開始編號，內文描述問題；以 `Type:` 記錄類型（`research`／`prototype`／`grilling`／`task`），以 `Status:` 記錄 `claimed`／`resolved`。
- **阻擋關係**：在檔案上方附近以 `Blocked by: NN, NN` 記錄。所列檔案都標記為 `resolved` 後，票據才算解除阻擋。
- **可執行票據**：掃描 `.scratch/<effort>/issues/`，找出未完成、無阻擋且尚未認領的檔案；依編號由小到大處理。
- **認領**：將狀態設為 `Status: claimed` 並儲存，再開始工作。
- **完成**：在 `## Answer` 標題下附上答案，將狀態設為 `Status: resolved`，再把脈絡連結（gist 與連結）附加到 `map.md` 的 Decisions-so-far。
