# OpenCode 專案上傳 CLI

此套件可獨立安裝於使用者本機，不需要安裝 Docker 或設定 OpenCode 管理密碼。

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
