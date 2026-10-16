# OpenCode 專案上傳與遠端 TUI CLI

此 CLI 以獨立執行檔透過 GitHub Releases 發佈。使用者安裝時不需要 Python、uv、Node.js 或 Docker；API 建立容器回應會依平台提供安裝命令。

## Windows PowerShell 安裝

執行建立容器回應中的 `cli_install_commands.windows_powershell`，或透過已授權的 `GET /api/opencode/cli-install-command?environment=windows` 取得安裝指令。指令會固定使用目前後端所選 Release 的 tag。

安裝至 `%LOCALAPPDATA%\Programs\opencode-project`，並加入使用者 PATH。

## macOS 安裝

執行建立容器回應中的 `cli_install_commands.macos`，或透過已授權的 `GET /api/opencode/cli-install-command?environment=mac` 取得安裝指令。指令會固定使用目前後端所選 Release 的 tag。

支援 Intel 與 Apple Silicon；執行檔安裝至 `~/.local/bin`。

## Linux 安裝

執行建立容器回應中的 `cli_install_commands.linux`，或透過已授權的 `GET /api/opencode/cli-install-command?environment=linux` 取得安裝指令；安裝腳本目前提供 Linux x64 執行檔，並安裝至 `~/.local/bin`。安裝指令依後端 `OPENCODE_CLI_CHANNEL` 選擇通道，並將安裝腳本與執行檔固定至同一個 Release tag。

## 發佈

推送以下任一格式的 Git tag，會由各自的 GitHub Actions workflow 建置並發布 CLI：

```sh
# 正式版
git tag cli-v1.2.3
git push origin cli-v1.2.3

# 開發版（使用唯一版本 tag，例如日期或遞增流水號）
git tag cli-dev-20261016.1
git push origin cli-dev-20261016.1
```

正式版使用 `cli-v*`，發布為一般 GitHub Release 並設為 Latest；開發版使用 `cli-dev-*`，發布為 Pre-release，且明確不會成為正式 Latest。工作流程只由對應 tag 推送觸發，不會因 dev 分支推送發布。請勿讓兩種通道共用 tag。

後端以 `OPENCODE_CLI_CHANNEL=prod`（預設）選正式版，以 `OPENCODE_CLI_CHANNEL=dev` 選開發版。切換後端通道不會自動替換已安裝的 CLI；使用者須重新取得並執行該通道提供的安裝指令。兩種通道沿用相同的 `opencode-project` 命令名稱。

兩個 workflow 都會在 Windows x64、macOS x64、macOS arm64 與 Linux x64 runner 上執行 CLI 測試、建置獨立執行檔並執行 `--help`。建置成功後先建立 draft Release，確認六項資產齊全再公開：

- `opencode-project-windows-x64.exe`
- `opencode-project-macos-x64`
- `opencode-project-macos-arm64`
- `opencode-project-linux-x64`
- `install.ps1`
- `install.sh`

Release 使用觸發 workflow 的原始 tag；任何平台測試、建置或資產檢查失敗時，Release 不會從 draft 公開。推送 tag 後請在 GitHub Actions 確認對應 workflow 成功，再查看該 tag 的 Release 與六項資產。此文件與 workflow 契約已在本機檢查；本次尚未推送 tag，GitHub Actions 實際執行及遠端 Release 尚未驗證。

## 上傳專案

建立容器 API 回應會提供專屬的 `upload_url`、`upload_token` 與完整上傳指令。可直接在專案根目錄執行該指令，或自行指定資料夾：

```sh
opencode-project upload --url "<upload_url>" --token "<upload_token>" --project ./my-project
```

CLI 的上傳請求只送往指定容器的 Tunnel，不會連線至管理 API。若 Tunnel URL 過期或發生網路錯誤，請由管理者透過受保護的列表/單筆管理 API 重新取得目前 `upload_url`，並使用建立容器時的原 upload token 重跑命令；重試可建立新的上傳工作階段並重新傳送檔案/區塊。CLI 不提供 `--refresh-url`。

未指定 `--project` 時使用目前目錄。CLI 會保留 `.git` 歷史與 remote（移除 remote URL 內的密碼），並略過 `node_modules`、虛擬環境、編譯產物與常見快取目錄；失敗時會自動重試三次，再次執行相同指令即可重傳。成功後檔案位於該容器的 `/workspace/project`。上傳授權資訊只適用於建立回應中的目標容器，請勿公開分享。

SSH remote 使用本機目前可用的 `SSH_AUTH_SOCK` agent 身分。上傳確認只傳送 SSH remote 綁定資訊，不會讀取、匯出或傳送私鑰；已載入 agent 的加密私鑰可正常使用。遠端簽章請求只會在 CLI `connect` 的 TUI 工作階段啟用時，透過同一容器 Tunnel 上以 connect token 驗證的 `/ssh-agent` WebSocket 即時轉送，連線中斷時容器端 socket 隨即關閉並移除。容器的 SSH wrapper 僅允許上傳專案所設定的 user、host、port、repository path 與 Git upload/receive-pack 命令；其他 SSH 目的地會被拒絕。若只上傳而未連線，遠端 Git push 不會取得本機 agent。HTTPS remote 內的 userinfo 及 SSH URL 中的密碼會在封裝或確認提示中移除；SCP-style SSH remote 則保留 SSH 使用者、主機與路徑。

CLI 使用隨執行檔打包的公開 CA 憑證驗證 HTTPS 上傳與 WSS 遠端 TUI 連線。若網路使用公司代理或自訂 CA，請先將 `SSL_CERT_FILE` 設為 PEM 格式的受信任 CA 憑證檔，再執行上傳或連線命令。

## 連入遠端 TUI

建立容器 API 回應會提供容器專屬的 `connect_url`、`connect_token` 與完整連線指令。連線透過 WebSocket 將本機終端與容器中的 OpenCode TUI 互動轉送；授權 token 放在 WebSocket handshake 的 Bearer header，不會暴露於 URL。若本機 SSH agent 可用，CLI 另開同一 Tunnel 的 agent relay WebSocket，僅中繼有大小上限的 SSH agent 封包，不接觸私鑰內容。部署使用 HTTPS 時 API 會提供 WSS 連線網址。

```sh
opencode-project connect --url "<connect_url>" --token "<connect_token>"
```

若需要 SSH agent forwarding，可用 `--project ./my-project` 指定已上傳的本機專案；CLI 會顯示遮蔽後的 SSH remote，並在每次連線前詢問是否只於該 TUI 工作階段啟用 relay。也可在上傳指令加上 `--connect-url "<connect_url>" --connect-token "<connect_token>"`，上傳時確認傳送 SSH agent forwarding 後，上傳成功即進入 TUI。連線中斷後重新執行 `connect` 即可重連；同一容器同時只接受一個遠端 TUI 工作階段。

TUI WebSocket 只連至指定容器 Tunnel。若 URL 過期或網路連線失敗，請透過管理 API 重新查詢目前 `connect_url`，並以原 connect token 重跑 `connect`。

遠端 TUI 的程序執行在容器內，無法直接讀取本機剪貼簿。從檔案總管、Finder 或檔案管理器複製一般檔案/圖片後，在 TUI 貼上，CLI 會讀取本機剪貼簿並透過已授權的 TUI WebSocket 傳送檔案，接著將 `@clipboard-...` 參照貼入目前 prompt。多個已複製檔案會一併傳送；檔案會以 `clipboard-` 前綴保存在容器專案目錄，方便 OpenCode 的 `@` 檔案搜尋找到。

一般貼上使用 `Ctrl+V`；若終端攔截該快捷鍵，可在複製檔案後按 `F9`（或 `Ctrl+G`）觸發貼上。剪貼簿讀取支援 Windows、macOS 與 Linux Wayland/X11；Linux 需安裝 `wl-paste` 或 `xclip`。每個檔案上限 25 MiB，每次最多 16 個檔案，總量上限 100 MiB。
