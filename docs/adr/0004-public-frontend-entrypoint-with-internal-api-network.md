# 公開前端入口與容器內部 API 網路

正式部署以前端服務直接綁定主機 `0.0.0.0:3000` 作為瀏覽器入口，前端 Nginx 將 `/api/` 經 Compose 內部網路代理至 API 後端；後端容器不發布 host port。這代表管理 API 可經公開前端入口存取，故由既有 `OPENCODE_ADMIN_TOKEN` 驗證管理請求；此部署入口決策取代 ADR 0003 對部署管理 API 僅限內網的限制，但不改變 CLI 專案上傳與遠端 TUI 經各容器 Tunnel 的資料路徑。
