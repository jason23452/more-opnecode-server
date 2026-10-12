# Features Base

React + Vite 前端與 FastAPI 後端的起始專案。前後端分開管理套件與啟動流程，並以 Feature 為單位擴充功能。

## 專案結構

```text
.
├── frontend/    # React、Vite、TypeScript 前端
└── backend/     # FastAPI、Python、uv 後端
```

## 開發環境需求

- Node.js 與 npm
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

## 啟動開發伺服器

在兩個終端機分別啟動：

```bash
cd frontend
npm install
npm run dev
```

```bash
cd backend
uv sync --dev
uv run uvicorn src.App.Main:app --reload --host 0.0.0.0 --port 8000
```

前端網址：<http://localhost:3000>  
後端 API：<http://localhost:8000/api>  
API 文件：<http://localhost:8000/docs>

後端預設允許來自 `http://localhost:3000` 與 `http://127.0.0.1:3000` 的 CORS 請求。

## 專案說明

- [前端架構、runtime config 與 API client](frontend/README.md)
- [後端架構、uv 指令與錯誤回應格式](backend/README.md)

## 開發原則

- 前端以 `App / Features / Shared` 分層，路由對應 Feature。
- 後端以 `App / Features / Shared` 分層，路由、schema 與功能邏輯放在所屬 Feature。
- 共用狀態、API client、UI 與錯誤處理集中於 Shared。
- 前端部署環境值由 runtime config 提供；後端設定由環境變數或 `.env` 提供。
