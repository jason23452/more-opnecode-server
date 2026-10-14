# 私人 Git 專案上傳與遠端推送

Status: ready-for-agent

## Problem Statement

使用者目前可在本機對私人 Git 專案進行提交與推送，但透過 CLI 將專案上傳至 OpenCode 容器後，遠端工作目錄缺少 `.git`，也沒有本機已使用的 HTTPS Git 認證。OpenCode agent 因此無法延續專案版本脈絡或直接將完成的變更推回私人遠端儲存庫，使用者必須另行處理 Git 歷史與認證。

## Solution

CLI 上傳私人專案時保留 Git 專案歷史，並偵測該 remote 使用的 HTTPS 或 SSH 認證來源。CLI 在傳送認證前詢問使用者確認；使用者可選擇傳送認證並上傳、只上傳專案，或取消。確認後，認證透過容器專屬 Tunnel 傳送至容器。上傳完成後，容器中的 Git 可使用該認證推送變更，使用者不需手動複製 token 或設定遠端認證。

Git 認證憑證由容器在其工作期間持有，並在容器移除時清除；憑證不寫入專案的 `.git/config` 或專案上傳封裝。CLI 必須以 HTTPS/TLS 傳送認證，並使用既有的容器專屬 upload 授權保護 Tunnel 請求。

## User Stories

1. 作為私人 Git 專案的使用者，我想上傳時保留 `.git`，以便遠端 agent 能接續目前分支、提交歷史與 remote。
2. 作為已能在本機推送私人 repo 的使用者，我想 CLI 自動偵測該 remote 所用的本機認證來源，以便不必手動複製帳密、token 或 SSH 認證。
3. 作為使用 HTTPS remote 的使用者，我想遠端容器能以該 remote 的認證執行 `git push`，以便 agent 完成修改後可直接推版。
4. 作為使用 SSH remote 的使用者，我想遠端容器能使用該 remote 的 SSH 認證執行 `git push`，以便 SSH 專案也能在遠端延續開發。
5. 作為使用者，我想在 CLI 傳送 Git 認證前看到 remote 與認證方式並明確確認，以便知道哪些 Git 權限會交給目標容器。
6. 作為使用者，我想在確認提示中選擇「傳送認證並上傳」、「只上傳專案（不帶認證）」或「取消」，以便依當次工作需求決定是否授權遠端推送。
7. 作為使用者，我想確認提示遮蔽 remote 中可能存在的敏感資訊，以免憑證或 URL 內的秘密直接顯示在終端或記錄中。
8. 作為使用者，我想認證只套用於上傳專案的 Git remote，以降低憑證被其他遠端服務意外使用的可能性。
9. 作為使用者，我想認證不被寫入 `.git/config` 或專案檔案，以免憑證隨版本控制或後續專案封裝散播。
10. 作為使用者，我想認證透過目前容器專屬 Tunnel 傳送，以便沿用既有的容器授權與 TLS 傳輸路徑。
11. 作為使用者，若本機認證來源無法提供該 remote 的認證，我想看到明確提示並仍可選擇只上傳專案或取消，以便上傳行為可預期。
12. 作為使用者，我想保留不含 Git repository 的一般資料夾上傳能力，以便既有使用方式不受影響。
13. 作為使用者，我想大型專案仍能使用現有分塊上傳流程，以便 Git 歷史與專案檔案不會繞過既有傳輸限制。
14. 作為使用者，我想容器移除時清除其中的 Git 認證，以縮短憑證在遠端環境中的存留時間。
15. 作為使用者，我想在上傳成功後立即使用遠端 TUI 操作專案並推送，以便同一個 CLI 流程完成上傳與遠端開發。
16. 作為使用者，我想 HTTPS 與 SSH 都沿用本機 Git 實際使用的認證來源，以便 CLI 不綁定單一 Git 服務供應商。

## Implementation Decisions

- Git 專案歷史是專案上傳內容的一部分；CLI 不再一律排除 `.git`。仍排除大型依賴、建置產物與快取目錄。
- CLI 偵測 Git remote 使用 HTTPS 或 SSH，並沿用本機 Git 已配置的認證來源；HTTPS 認證透過 Git credential helper 取得，不自行解析 Git Credential Manager、GitHub CLI 等工具的內部儲存格式；SSH 僅使用目前可用 OpenSSH agent endpoint（POSIX `SSH_AUTH_SOCK` 或 Windows OpenSSH named pipe）中已載入的身分，不讀取或匯出私鑰檔案。
- 傳送任何 Git 認證前，CLI 必須在終端顯示遮蔽敏感資訊的 remote 與認證類型，並提供「傳送認證並上傳」、「只上傳專案（不帶認證）」及「取消」選項。非互動式終端不得默認傳送認證。
- HTTPS 認證與專案封裝分開傳送至目標容器，使用容器專屬 Tunnel URL 與 upload token，且傳輸需使用 HTTPS/TLS。SSH 上傳只傳送 SSH remote 綁定資訊，不傳送私鑰或 agent identity 私密材料。
- 容器端將 HTTPS 認證關聯至上傳專案的 HTTPS remote；SSH remote 使用容器端嚴格限制目的地與 Git 命令的 wrapper，並只在 CLI TUI 工作階段存活期間提供暫時 agent socket。
- HTTPS 認證可在容器工作期間使用並於容器移除時清除。SSH 簽章請求只在 CLI connect WebSocket 存活期間經同一 Tunnel 上以 connect token 驗證的窄用途 WebSocket relay 送至本機 agent；斷線時容器端關閉並刪除 socket，之後 SSH push 必須重新連線。
- 專案檔案仍經目標容器 Tunnel 直接上傳，管理後端不代理專案或 Git 認證 payload，遵循既有專案上傳資料路徑決策。
- CLI 的整體 upload 流程是主要行為 seam；認證取得與容器端接收/套用/清除需可獨立驗證，以涵蓋失敗與生命週期行為。
- 支援 HTTPS 與 SSH remote；其他 Git 傳輸協定不在此規格內。

## Testing Decisions

- 測試以外部可觀察行為為主：上傳後遠端保有 Git 歷史；HTTPS 可實際推送；SSH 只在已連線且本機 agent 可用時能對設定 remote 推送，且 disconnect 後再次 push 不得成功；私鑰不出現在專案封裝、Tunnel payload 或容器檔案；disconnect 後 relay socket 清除；HTTPS 認證在容器移除時隨容器工作資料一併消失。
- CLI 測試涵蓋 upload 整體流程，包括辨識 HTTPS/SSH Git remote、由相應本機認證來源取得認證、提示選項及各選項的結果、認證與專案分離傳輸、一般非 Git 資料夾相容性，以及認證不可取得時仍可只上傳專案或取消。
- 容器測試涵蓋 HTTPS 認證授權、remote 關聯及清除；SSH 測試涵蓋真實 agent protocol 簽章請求、local bare remote push、未授權 remote 拒絕，以及 disconnect 清理。
- 使用既有 CLI upload 測試與後端 upload receiver 測試作為測試先例；優先沿用現有 HTTP/Tunnel 與臨時檔案測試方式，不以單元測試驗證私有實作細節。SSH agent 封包允許清單在 CLI 與容器 relay 兩端獨立驗證，因為兩者是不同程序與信任邊界：CLI 保護本機 agent，容器 relay 保護遠端 relay；任何一端不得假設另一端一定執行驗證。
- 驗證範圍包含小型與分塊專案上傳，確認兩種傳輸模式都不會遺漏或混入認證 payload。

## Out of Scope

- Git remote 使用 HTTPS 或 SSH 以外傳輸協定的認證。
- 管理多個 Git remote、互動式切換認證帳號或使用者在遠端手動輸入憑證。
- 為本機 Git credential helper 建立或更新帳號、登入狀態與權限範圍。
- 由管理後端保存、代理或管理 Git 認證。
- 將 Git 認證長期保存至跨容器的服務端帳號或共享憑證庫。

## Further Notes

- Tunnel token 用於授權對容器 Tunnel 的存取，HTTPS/TLS 負責傳輸加密；兩者用途不同。HTTPS credential 由容器在工作期間使用；SSH agent protocol 僅於本機 CLI connect 工作階段即時中繼。
- 本機 credential helper 提供的憑證權限與效期由該 helper 及遠端 Git 服務決定；本功能不承諾將長效憑證自動轉換為短效或 repo-scoped token。
- 專案封裝包含 `.git` 歷史，並在封裝時移除 remote URL 內的認證 userinfo。加密私鑰由使用者在本機解鎖並載入 agent 後使用；私鑰不離開本機。
