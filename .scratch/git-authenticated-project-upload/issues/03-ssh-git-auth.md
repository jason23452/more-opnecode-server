# 03: 確認並傳送 SSH Git 認證

**What to build:** 使用者上傳 SSH Git 專案時，CLI 偵測本機 OpenSSH agent 並在啟用轉送前取得確認；私鑰留在本機，遠端容器在 CLI TUI 連線期間透過 Tunnel 請求本機 agent 簽章，以便推送至原 SSH remote。轉送在連線中斷時終止，並遵循與 HTTPS 相同的 remote 限制與提示規則。

**Blocked by:** 01: 上傳時保留 Git 專案歷史; 02: 確認並傳送 HTTPS Git 認證.

**Status:** resolved

- [x] CLI 能辨識 SSH Git remote，並沿用本機目前可用的 OpenSSH agent 身分；支援 Unix agent socket 與 Windows OpenSSH agent named pipe。
- [x] CLI 使用與 HTTPS 一致的確認流程，顯示遮蔽敏感資訊的 remote 與 SSH agent 轉送類型，提供傳送認證並上傳、只上傳專案及取消選項。
- [x] 非互動式終端不會默認轉送 SSH agent；若本機 agent 不可用，使用者仍可選擇只上傳專案或取消，並收到清楚說明。
- [x] 上傳只傳送 remote 綁定資訊，不傳私鑰；使用者確認後，agent 簽章請求透過 HTTPS/TLS 與容器專屬 connect token 在 TUI Tunnel 工作階段中即時轉送。
- [x] 遠端 Git 可透過 SSH agent relay 對已授權的原 SSH remote 執行推送；其他 host、repo path 或命令遭拒絕。
- [x] TUI 連線中斷時關閉並刪除 relay socket，且已驗證斷線後 push 失敗；重新連線時才會再次建立 relay。
- [x] CLI 整體 upload 行為與容器端測試驗證確認選項、真實 agent protocol 簽章、local bare remote push、未授權目的地拒絕及斷線清理。
