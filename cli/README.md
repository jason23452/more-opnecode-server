# OpenCode 專案上傳與遠端 TUI CLI

此 CLI 原始碼隨本儲存庫一同提供；可在儲存庫 checkout 根目錄安裝至使用者本機，不需要安裝 Docker 或設定 OpenCode 管理密碼。API 建立容器回應中的安裝指令也需在 checkout 根目錄執行。

## 安裝

在儲存庫根目錄執行 API 建立回應中的安裝指令：

```sh
python -m pip install ./cli
```

## 上傳專案

建立容器 API 回應會提供專屬的 `upload_url`、`upload_token` 與完整上傳指令。可直接在專案根目錄執行該指令，或自行指定資料夾：

```sh
opencode-project upload --url "<upload_url>" --token "<upload_token>" --project ./my-project
```

未指定 `--project` 時使用目前目錄。CLI 預設略過 `.git`、`node_modules`、虛擬環境、編譯產物與常見快取目錄；失敗時會自動重試三次，再次執行相同指令即可重傳。成功後檔案位於該容器的 `/workspace/project`。上傳授權資訊只適用於建立回應中的目標容器，請勿公開分享。

## 連入遠端 TUI

建立容器 API 回應會提供容器專屬的 `connect_url`、`connect_token` 與完整連線指令。連線透過 WebSocket 將本機終端與容器中的 OpenCode TUI 互動轉送；授權 token 放在 WebSocket handshake 的 Bearer header，不會暴露於 URL。部署使用 HTTPS 時 API 會提供 WSS 連線網址。

```sh
opencode-project connect --url "<connect_url>" --token "<connect_token>"
```

也可在上傳指令加上 `--connect-url "<connect_url>" --connect-token "<connect_token>"`，上傳成功後自動進入 TUI。連線中斷後重新執行 `connect` 即可重連；同一容器同時只接受一個遠端 TUI 工作階段。
