# Features Base API

使用 FastAPI 建立的功能導向 API 起始專案，依 `App / Features / Shared` 三層組織程式碼，使用 uv 管理依賴與虛擬環境。

## 環境需求

- Python 3.12（版本由 `.python-version` 固定）
- [uv](https://docs.astral.sh/uv/)

## 安裝與啟動

若同一份工作目錄會在 Windows 與 WSL 間切換，請在 Windows PowerShell 使用獨立的 uv 環境路徑，避免兩種作業系統共用 `.venv`：

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:LOCALAPPDATA\uv\more-opnecode-server-backend-win"
uv python install 3.12
uv sync --dev
uv run uvicorn src.App.Main:app --reload --host 0.0.0.0 --port 8000
```

```bash
uv sync --dev
cp .env.example .env # Windows PowerShell: Copy-Item .env.example .env
uv run uvicorn src.App.Main:app --reload --host 0.0.0.0 --port 8000
```

API 根路徑預設為 `/api`：

- Health check：<http://localhost:8000/api/health>
- Swagger UI：<http://localhost:8000/docs>
- ReDoc：<http://localhost:8000/redoc>

uv 會依 `pyproject.toml` 建立 `.venv` 並安裝依賴；`uv.lock` 鎖定完整解析版本。新增依賴請使用 `uv add <package>`；開發依賴使用 `uv add --dev <package>`，並將更新後的 lockfile 一併保留。

## 架構

```text
src/
├── App/
│   ├── Main.py                  # 建立 FastAPI app、middleware 與 router
│   └── Settings.py              # 環境變數及應用程式設定
├── Features/
│   └── Health/
│       ├── Router.py            # Feature API 路由
│       └── Schema.py            # Feature request/response schema
└── Shared/
    ├── Errors/                  # ApiError、錯誤 schema、集中 exception handlers
    └── Middleware/              # 跨請求共用 middleware
```

新增功能時，在 `src/Features/<FeatureName>/` 建立該 Feature 的 Router、Schema 與服務邏輯，再將 Router 掛載到 `src/App/Main.py`。僅跨 Feature 共用的能力放在 `Shared/`。

## 設定

複製 `.env.example` 為 `.env`，可調整以下設定：

| 變數 | 預設值 | 說明 |
| --- | --- | --- |
| `APP_NAME` | `Features Base API` | OpenAPI 文件中的服務名稱 |
| `API_PREFIX` | `/api` | API 路由前綴 |
| `DEBUG` | `false` | FastAPI debug 模式 |
| `FRONTEND_ORIGINS` | `http://localhost:3000` 與 `http://127.0.0.1:3000` | CORS 允許來源，使用 JSON 字串陣列 |
| `OPENCODE_PASSWORD` | 空字串 | OpenCode 服務共用密碼；未設定時建立容器會失敗 |
| `OPENCODE_ADMIN_TOKEN` | 空字串 | 管理 API Bearer Token；未設定時管理 API 一律拒絕 |
| `OPENCODE_CONTAINER_CPU` | `1.0` | 單一容器 CPU 上限 |
| `OPENCODE_CONTAINER_MEMORY` | `2g` | 單一容器記憶體上限 |
| `OPENCODE_MAX_CONTAINERS` | `4` | 同時執行容器上限 |
| `OPENCODE_STARTUP_TIMEOUT` | `180` | OpenCode 與 Quick Tunnel 初始化秒數上限 |
| `OPENCODE_IMAGE` | `dynamic-opencode:latest` | 固定 OpenCode 容器映像標籤 |
| `OPENCODE_TUNNEL_PROBE_INTERVAL` | `30` | Tunnel 外部健康探測間隔（秒） |
| `OPENCODE_TUNNEL_FAILURE_THRESHOLD` | `3` | 觸發 Tunnel 重建前的連續探測失敗次數 |
| `OPENCODE_TUNNEL_RECOVERY_ATTEMPTS` | `3` | 每輪 Tunnel 重建嘗試次數 |
| `OPENCODE_TUNNEL_RECOVERY_DELAY` | `2` | 重建失敗後的等待秒數 |
| `OPENCODE_TUNNEL_RETRY_INITIAL_DELAY` | `5` | cloudflared 建立失敗（包含 Quick Tunnel 回覆 429）後首次重試等待秒數，採指數退避 |
| `OPENCODE_TUNNEL_RETRY_MAX_DELAY` | `60` | cloudflared 指數退避的最長等待秒數 |
| `OPENCODE_UPLOAD_MAX_BYTES` | `99614720`（95 MiB） | 單一上傳請求上限；必須介於 1 byte 至 95 MiB，超過會在 API 設定載入時拒絕。容器 ingress 的 nginx 上限固定為 95 MiB，分塊請求不超過 8 MiB。 |
| `OPENCODE_CLI_RELEASE_URL` | GitHub 最新 Release assets 網址 | 容器建立回應中各平台 CLI 安裝指令使用的下載來源 |

範例：

```env
FRONTEND_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
OPENCODE_PASSWORD=replace-with-a-secret
OPENCODE_ADMIN_TOKEN=replace-with-an-internal-token
```

管理端點 `POST /api/opencode/containers` 需帶 `Authorization: Bearer <OPENCODE_ADMIN_TOKEN>`。成功回傳 `201`，包含 `id`、OpenCode `url`、`upload_url`、`upload_token`、`cli_install_commands`（`windows_powershell`、`macos`、`linux`）、`upload_command`、`connect_url`、`connect_token` 與 `connect_command`；若初始化失敗或達容器數量上限，回傳 `503`。受保護的容器列表與單筆 GET 會回傳目前 `upload_url` 與 `connect_url`，不帶 `environment` 時不回傳 token 或指令；單筆 GET 可加 `environment=windows|mac|linux`，回傳該平台的 `upload_command` 與 `connect_command`。這兩個指令含容器專屬授權 token，應視同密碼保護。`GET /api/opencode/cli-install-command?environment=windows|mac|linux` 以同一管理者 Bearer 授權回傳 `environment` 與該平台的 CLI 安裝指令。`upload-target` 控制端點已移除。API 不回傳 OpenCode 密碼。各平台安裝指令會從 `OPENCODE_CLI_RELEASE_URL` 下載 GitHub Release 中的獨立執行檔，使用者不需要 Python、uv 或 Node.js。建立符合 `cli-v*` 格式的 Git tag 會觸發 CLI 建置及 Release 發佈流程。Windows 上透過 Docker Desktop 使用時，WSL 後端可自動選用 `docker.exe`，不需 WSL Docker CLI 或啟用 WSL Integration。

CLI 安裝後先執行回應中的 `upload_command`，即可將目前專案上傳至容器 `/workspace/project`；再執行 `connect_command` 進入遠端 TUI。也可使用支援的 `--connect-url` 與 `--connect-token` 選項，在上傳後直接連線。CLI 的上傳與 TUI 流量只連至容器 Tunnel，失敗時不會呼叫管理 API；請重新查詢目前 Tunnel URL，並以原容器 token 重跑命令。

真實 Docker/Cloudflare 黑箱測試需可用 Docker daemon 與外網，設定 `OPENCODE_DOCKER_E2E=1` 後執行 `uv run pytest tests/test_opencode_docker_e2e.py -v`。測試會啟動實際後端，呼叫管理 API，驗證 stale URL 不觸發 CLI 管理端刷新、96 MiB 專案在以新查詢 URL 和原 token 重試後上傳、TUI 直連及容器隔離，並驗證 Tunnel 故障後 URL 更新且原容器工作資料保留，最後清理測試容器。

## 統一錯誤回應

所有錯誤由 `Shared/Errors/ExceptionHandlers.py` 正規化，格式如下：

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "請求參數驗證失敗",
    "details": [
      { "field": "body.email", "message": "Field required", "type": "missing" }
    ]
  },
  "request_id": "a-request-uuid"
}
```

已統一處理：

- `ApiError`：業務邏輯預期錯誤。
- FastAPI request validation error：回傳 `422` 與欄位錯誤清單。
- HTTP exception：回傳對應 HTTP status 與 `HTTP_<status>` 錯誤代碼。
- 未預期 exception：回傳 `500 INTERNAL_SERVER_ERROR`，不洩露內部例外內容。

每個 request 都有 `X-Request-ID` response header；呼叫端可傳入自己的 `X-Request-ID`，此 ID 也會放進錯誤 response 的 `request_id`。

在 Feature 中拋出業務錯誤：

```python
from src.Shared.Errors.ApiError import ApiError

raise ApiError(
    status_code=404,
    code="USER_NOT_FOUND",
    message="找不到使用者",
    details={"user_id": user_id},
)
```

## 測試與檢查

開發依賴已包含 pytest 與 httpx：

```bash
uv run pytest
uv run python -m compileall -q src
```
