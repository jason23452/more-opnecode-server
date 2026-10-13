# 09: 透過容器 Tunnel 直接連入遠端 TUI

**What to build:** 讓本機 CLI 透過目標容器的 Tunnel ingress 直接連入容器內的 OpenCode TUI；管理後端不代理終端資料，也不負責啟動互動式 TUI 程序。

**Blocked by:**
- 06: 透過本機 CLI 連入遠端 OpenCode TUI.
- 07: 透過容器 Tunnel 直接上傳專案.

**Status:** ready-for-agent

- [ ] 建立容器 API 回應提供該容器 Tunnel 上的 `connect_url` 與專屬連線 token；網址不指向後端或 `localhost`。
- [ ] 容器內執行受 token 保護的互動式 TUI relay；Tunnel ingress 將 WebSocket `/connect` 路徑導向此 relay，其他 OpenCode 請求仍導向 OpenCode server。
- [ ] 本機 CLI 的獨立 `connect` 與 upload-then-connect 流程都直接連入 Tunnel；TUI 輸入、輸出與終端結束不經管理後端。
- [ ] 單一容器同時僅允許一個 TUI 工作階段；授權錯誤、忙碌與中斷提供可理解回饋，且可以重新連線。
- [ ] 移除管理後端的 TUI WebSocket relay 與為 TUI 執行 `docker exec` 的路徑。
- [ ] 以本機 CLI、內網管理 API、Windows Docker Desktop/WSL 與實際容器驗證 Tunnel TUI 互動、session 互斥、斷線與重連；OpenCode server 仍可透過同一 Tunnel 使用。
