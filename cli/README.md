# OpenCode 專案上傳與遠端 TUI CLI

此 CLI 以獨立執行檔透過 GitHub Releases 發佈。使用者安裝時不需要 Python、uv、Node.js 或 Docker；API 建立容器回應會依平台提供安裝命令。

## Windows PowerShell 安裝

執行建立容器回應中的 `cli_install_commands.windows_powershell`。也可直接下載並執行安裝腳本：

```powershell
irm 'https://github.com/jason23452/more-opnecode-server/releases/latest/download/install.ps1' | iex
```

安裝至 `%LOCALAPPDATA%\Programs\opencode-project`，並加入使用者 PATH。

## macOS 安裝

執行建立容器回應中的 `cli_install_commands.macos`，或使用：

```sh
curl -fsSL 'https://github.com/jason23452/more-opnecode-server/releases/latest/download/install.sh' | sh
```

支援 Intel 與 Apple Silicon；執行檔安裝至 `~/.local/bin`。

## Linux 安裝

執行建立容器回應中的 `cli_install_commands.linux`；安裝腳本目前提供 Linux x64 執行檔，並安裝至 `~/.local/bin`。

## 發佈

推送符合 `cli-v*` 格式的 Git tag（例如 `cli-v0.1.0`）會觸發 GitHub Actions，建置 Windows x64、macOS Intel/Apple Silicon 與 Linux x64 執行檔，並連同安裝腳本附加至該 GitHub Release。安裝指令下載 latest Release 的對應資產。

## 上傳專案

建立容器 API 回應會提供專屬的 `upload_url`、`upload_token` 與完整上傳指令。可直接在專案根目錄執行該指令，或自行指定資料夾：

```sh
opencode-project upload --url "<upload_url>" --token "<upload_token>" --project ./my-project
```

CLI 的上傳請求只送往指定容器的 Tunnel，不會連線至管理 API。若 Tunnel URL 過期或發生網路錯誤，請由管理者透過受保護的列表/單筆管理 API 重新取得目前 `upload_url`，並使用建立容器時的原 upload token 重跑命令；重試可建立新的上傳工作階段並重新傳送檔案/區塊。CLI 不提供 `--refresh-url`。

未指定 `--project` 時使用目前目錄。CLI 預設略過 `.git`、`node_modules`、虛擬環境、編譯產物與常見快取目錄；失敗時會自動重試三次，再次執行相同指令即可重傳。成功後檔案位於該容器的 `/workspace/project`。上傳授權資訊只適用於建立回應中的目標容器，請勿公開分享。

CLI 使用隨執行檔打包的公開 CA 憑證驗證 HTTPS 上傳與 WSS 遠端 TUI 連線。若網路使用公司代理或自訂 CA，請先將 `SSL_CERT_FILE` 設為 PEM 格式的受信任 CA 憑證檔，再執行上傳或連線命令。

## 連入遠端 TUI

建立容器 API 回應會提供容器專屬的 `connect_url`、`connect_token` 與完整連線指令。連線透過 WebSocket 將本機終端與容器中的 OpenCode TUI 互動轉送；授權 token 放在 WebSocket handshake 的 Bearer header，不會暴露於 URL。部署使用 HTTPS 時 API 會提供 WSS 連線網址。

```sh
opencode-project connect --url "<connect_url>" --token "<connect_token>"
```

也可在上傳指令加上 `--connect-url "<connect_url>" --connect-token "<connect_token>"`，上傳成功後自動進入 TUI。連線中斷後重新執行 `connect` 即可重連；同一容器同時只接受一個遠端 TUI 工作階段。

TUI WebSocket 只連至指定容器 Tunnel。若 URL 過期或網路連線失敗，請透過管理 API 重新查詢目前 `connect_url`，並以原 connect token 重跑 `connect`。

遠端 TUI 的程序執行在容器內，無法直接讀取本機剪貼簿。從檔案總管、Finder 或檔案管理器複製一般檔案/圖片後，在 TUI 貼上，CLI 會讀取本機剪貼簿並透過已授權的 TUI WebSocket 傳送檔案，接著將 `@clipboard-...` 參照貼入目前 prompt。多個已複製檔案會一併傳送；檔案會以 `clipboard-` 前綴保存在容器專案目錄，方便 OpenCode 的 `@` 檔案搜尋找到。

一般貼上使用 `Ctrl+V`；若終端攔截該快捷鍵，可在複製檔案後按 `F9`（或 `Ctrl+G`）觸發貼上。剪貼簿讀取支援 Windows、macOS 與 Linux Wayland/X11；Linux 需安裝 `wl-paste` 或 `xclip`。每個檔案上限 25 MiB，每次最多 16 個檔案，總量上限 100 MiB。
