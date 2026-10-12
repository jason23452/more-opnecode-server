# 使用 Docker OpenCode 容器與 Cloudflare Quick Tunnel

後端以同主機 Docker 建立固定規格的 OpenCode 容器，並在容器內執行 `cloudflared` 建立臨時 Quick Tunnel，將外部請求導向容器的 `4096` port。選擇此方式是為了由後端直接管理容器與其 Tunnel 生命週期，並免除固定自訂網域的前置需求；代價是 Tunnel URL 可能在重建時改變，故後端必須監控健康狀態並提供查詢最新 URL 的能力。
