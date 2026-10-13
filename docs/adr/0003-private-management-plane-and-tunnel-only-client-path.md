# 內網管理後端與 Tunnel 用戶端資料路徑分離

管理 API 保留在內網，只供管理者建立/查詢/刪除容器及取得目前 Tunnel URL；本機 CLI 的專案上傳與遠端 TUI 都直接經各容器的 Tunnel ingress，不連線至 `localhost:8000` 或其他管理 API 位址。這讓對外暴露面僅包含各容器 Tunnel，但 Quick Tunnel URL 改變時，CLI 無法自行查詢後端，因此管理者須從內網管理 API 取得新 URL 並重新執行 CLI 命令；TUI PTY relay 也必須在容器內運作。
