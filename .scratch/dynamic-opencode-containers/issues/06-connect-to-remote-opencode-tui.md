# 06: 透過本機 CLI 連入遠端 OpenCode TUI

**What to build:** 讓使用者從本機終端連入指定容器的互動式 OpenCode TUI，並可選擇先上傳專案再直接進入 TUI。

**Blocked by:** 05: 透過本機 CLI 上傳專案資料夾至容器.

**Status:** ready-for-human

- [ ] 建立 API 回應提供該容器專屬的 CLI 連線指令與授權資訊；連線不要求使用者在本機持有 Docker 權限或 OpenCode 管理密碼。
- [ ] 本機 CLI 可連入遠端容器中的 OpenCode TUI，並保留既有 OpenCode server 與 Tunnel 能力。
- [ ] 同一容器同時僅允許一個互動式 TUI 工作階段；其他連線會收到可理解的拒絕或忙碌回饋。
- [ ] CLI 提供獨立的連線操作，以及先上傳指定專案資料夾再連線的一鍵操作。
- [ ] 終端連線中斷時可辨識連線狀態並支援重新連線；驗證連線失敗及重新連線行為。
- [ ] 以本機 CLI、後端連線通道與實際容器驗證 TUI 互動、單一工作階段限制及一鍵上傳連線流程。此項尚未執行：Docker Desktop CLI 回報 `Docker Desktop is unable to start`，需先恢復 Docker Engine。
