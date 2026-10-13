# 07: 透過容器 Tunnel 直接上傳專案

**What to build:** 讓本機 CLI 將專案封裝直接傳至目標容器的 Tunnel upload endpoint；專案檔案內容不經管理後端。

**Blocked by:** 05: 透過本機 CLI 上傳專案資料夾至容器.

**Status:** ready-for-agent

- [ ] 建立容器 API 回應提供該容器 Tunnel ingress 上的 upload URL 與容器專屬 upload token。
- [ ] 容器 Tunnel ingress 將一般 OpenCode HTTP 流量送至 OpenCode server，並將 upload 路徑送至容器內接收器；OpenCode server 與 TUI 連線維持可用。
- [ ] 本機 CLI 將指定 project folder 封裝後，使用容器專屬 token 直接向 Tunnel upload URL 傳送檔案；管理後端不接收或轉送檔案 payload。
- [ ] 接收器只可寫入該容器的專案工作目錄，驗證 upload token 與封裝路徑；完成後才安全替換工作目錄，失敗時保留既有專案。
- [ ] 單次 Tunnel 請求超過允許大小時回傳清楚錯誤且不留下部分專案；大型專案分塊傳輸由 #08 支援。
- [ ] 以真實 Docker、Quick Tunnel、API 與 CLI 驗證直傳、工作目錄隔離、OpenCode server 可用，以及檔案 payload 不經管理後端。
