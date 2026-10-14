# 03: 確認並傳送 SSH Git 認證

**What to build:** 使用者上傳 SSH Git 專案時，CLI 偵測本機目前可用的 SSH 認證來源並在傳送前取得確認；確認後，遠端容器可使用該認證推送至原 SSH remote，並遵循與 HTTPS 相同的授權、提示及清除規則。

**Blocked by:** 01: 上傳時保留 Git 專案歷史; 02: 確認並傳送 HTTPS Git 認證.

**Status:** ready-for-agent

- [ ] CLI 能辨識 SSH Git remote，並沿用本機目前可用的 SSH 認證來源。
- [ ] CLI 使用與 HTTPS 一致的確認流程，顯示遮蔽敏感資訊的 remote 與 SSH 認證類型，提供傳送認證並上傳、只上傳專案及取消選項。
- [ ] 非互動式終端不會默認傳送 SSH 認證；若本機無法取得認證，使用者仍可選擇只上傳專案或取消，並收到清楚說明。
- [ ] 選擇傳送時，SSH 認證經 HTTPS/TLS 及目標容器專屬 upload 授權傳送，並只供該 SSH remote 使用；認證不寫入專案封裝或 `.git/config`。
- [ ] 遠端 Git 可使用已傳送的認證對原 SSH remote 執行推送。
- [ ] 容器移除時清除 SSH 認證；中斷 TUI 連線不會提前清除仍在使用中的認證。
- [ ] CLI 整體 upload 行為測試涵蓋確認選項與 SSH 認證不可取得情境；容器端測試驗證認證套用與清除行為。
