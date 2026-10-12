# 專案指引

- 本儲存庫的說明與新增文件請使用繁體中文。
- 前後端各自管理依賴：前端在 `frontend/`（npm），後端在 `backend/`（uv）；請在對應目錄執行命令。
- 本機開發需分別啟動前後端：前端 `npm run dev`（`http://localhost:3000`）；後端先 `uv sync --dev`，再執行 `uv run uvicorn src.App.Main:app --reload --host 0.0.0.0 --port 8000`。後端設定可複製 `backend/.env.example` 為 `.env`。
- 前端驗證：`cd frontend && npm run typecheck`；建置（已包含型別檢查）：`cd frontend && npm run build`。專案未定義 lint 或前端 test script。
- 後端驗證：`cd backend && uv run pytest`；單一測試可用 `uv run pytest tests/test_api.py -k <測試名稱>`。需要時另以 `uv run python -m compileall -q src` 檢查語法。
- 前後端均以 `App / Features / Shared` 分層；功能專屬程式碼留在 Feature，跨功能共用能力才放 Shared。前端新增路由需在 `frontend/src/App/Router/AppRouter.tsx` 註冊；後端新增 Router 需在 `backend/src/App/Main.py` 掛載。
- 前端 `@/` 指向 `frontend/src/`；部署時 API URL 由 `frontend/public/runtime-config.js` 提供，修改該檔不需重建。後端 API 預設前綴 `/api`，設定由環境變數或 `.env` 提供。
- 後端依賴以 `uv add` / `uv add --dev` 管理，變更依賴時一併提交更新的 `backend/uv.lock`；前端依賴使用 npm 並保留 `frontend/package-lock.json`。
- 更完整的架構與設定見 `README.md`、`frontend/README.md`、`backend/README.md`；以 `package.json`、`pyproject.toml` 等執行設定為準。
