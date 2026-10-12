# 領域文件

說明工程技能在探索程式碼庫時，如何讀取本儲存庫的領域文件。

## 探索前先閱讀

- 根目錄的 `GLOSSARY.md`；若根目錄有 `GLOSSARY-MAP.md`，則依其指向閱讀與目前主題相關的各份 `GLOSSARY.md`。
- `docs/adr/` 中與即將處理區域相關的 ADR。
- 本儲存庫採 single-context；若未來改採多領域脈絡，亦需檢查 `src/<context>/docs/adr/` 中各脈絡專屬的決策。

若上述檔案不存在，安靜地繼續，不需指出缺漏或預先建議建立。當術語或決策實際釐清後，由 `/domain-modeling`（可透過 `/grill-with-docs` 與 `/improve-codebase-architecture` 使用）按需建立。

## 檔案結構：single-context

```text
/
├── GLOSSARY.md
├── docs/adr/
└── src/
```

## 使用詞彙表中的術語

在輸出中提及領域概念時（例如 issue 標題、重構提案、假設或測試名稱），使用 `GLOSSARY.md` 定義的用語。不要改用詞彙表明確避免的同義詞。

若需要的概念尚未列入詞彙表，請重新確認這是否為專案實際使用的語言；若確有缺漏，記錄下來供 `/domain-modeling` 處理。

## 指出 ADR 衝突

若輸出內容與既有 ADR 相矛盾，請明確提出，而不要默默覆寫決策，例如：

> 與 ADR-0007（事件溯源訂單）相矛盾，但值得重新檢視，因為……
