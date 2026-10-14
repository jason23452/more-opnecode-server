# 02: 確認並傳送 HTTPS Git 認證

**What to build:** 使用者上傳 HTTPS Git 專案時，CLI 從本機 Git credential helper 取得該 remote 的認證，先顯示遮蔽敏感資訊的確認提示；確認傳送後，遠端容器可推送至該 remote，且容器移除時認證會清除。

**Blocked by:** 01: 上傳時保留 Git 專案歷史.

**Status:** ready-for-agent

- [ ] CLI 能辨識 HTTPS Git remote，並沿用本機 Git credential helper 取得該 remote 的認證，不解析 helper 的私有儲存格式。
- [ ] CLI 在送出認證前顯示遮蔽敏感資訊的 remote 與認證類型，提供「傳送認證並上傳」、「只上傳專案（不帶認證）」及「取消」選項。
- [ ] 非互動式終端不會默認傳送認證；若無法取得認證，使用者仍可選擇只上傳專案或取消，並收到清楚說明。
- [ ] 選擇傳送時，認證與專案封裝分開經 HTTPS/TLS 及目標容器專屬 upload 授權傳送，且只套用至該 HTTPS remote。
- [ ] 遠端 Git 可使用已傳送的認證對原 remote 執行推送；認證不寫入 `.git/config`、專案檔案或專案封裝。
- [ ] 容器移除時清除 Git 認證；單純中斷 TUI 連線不會提前清除仍在使用中的認證。
- [ ] CLI 整體 upload 行為測試涵蓋傳送、只上傳、取消、認證不可取得與傳輸失敗情境；容器端測試涵蓋認證授權、remote 關聯及清除生命週期。
