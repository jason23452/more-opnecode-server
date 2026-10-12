# 動態 OpenCode 容器

本領域涵蓋由後端管理的 OpenCode 容器，以及使用者透過網路連線至該容器的方式。

## Language

**OpenCode 容器**：執行 OpenCode 服務與其開發工具的獨立執行環境。
_Avoid_: 工作容器、沙箱（除非明確指安全隔離機制）

**Tunnel**：將外部網路請求轉送至 OpenCode 容器內服務的 Cloudflare 連線。
_Avoid_: 通道、代理（作為 Tunnel 的同義詞）

**Tunnel URL**：Cloudflare 為 Tunnel 提供、可由外部連線至 OpenCode 服務的網址。
_Avoid_: 容器網址（容器本身沒有對外 URL）

**容器健康狀態**：OpenCode 服務與其 Tunnel URL 是否可正常提供連線的狀態。
_Avoid_: 容器存活狀態（只代表容器程序存在，未必代表服務可用）

**容器工作資料**：OpenCode 容器執行期間使用的專屬檔案與工作目錄。
_Avoid_: 共用工作區（此需求中每個容器各自隔離）
