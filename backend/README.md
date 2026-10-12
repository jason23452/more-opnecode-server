# Features Base API

使用 FastAPI 建立的功能導向 API 起始專案，依 `App / Features / Shared` 三層組織程式碼，使用 uv 管理依賴與虛擬環境。

## 環境需求

- Python 3.10 以上
- [uv](https://docs.astral.sh/uv/)

## 安裝與啟動

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

範例：

```env
FRONTEND_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

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
