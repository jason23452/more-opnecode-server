# 動態 OpenCode 容器

本領域涵蓋由後端管理的 OpenCode 容器，以及使用者透過網路連線至該容器的方式。

## Language

**OpenCode 容器**：執行 OpenCode 服務與其開發工具的獨立執行環境。
_Avoid_: 工作容器、沙箱（除非明確指安全隔離機制）

**Tunnel**：將外部網路請求轉送至 OpenCode 容器內服務的 Cloudflare 連線。
_Avoid_: 通道、代理（作為 Tunnel 的同義詞）

**Tunnel URL**：Cloudflare 為 Tunnel 提供、可由外部連線至容器 Tunnel ingress 的網址。
_Avoid_: 容器網址（容器本身沒有對外 URL）

**Tunnel ingress**：容器接收 Tunnel 請求並將請求導向 OpenCode 服務、專案上傳或 TUI 工作階段的入口。
_Avoid_: 管理 API（管理 API 留在內網，不經 Tunnel 對外提供）

**容器健康狀態**：OpenCode 服務與其 Tunnel URL 是否可正常提供連線的狀態。
_Avoid_: 容器存活狀態（只代表容器程序存在，未必代表服務可用）

**容器工作資料**：OpenCode 容器執行期間使用的專屬檔案與工作目錄。
_Avoid_: 共用工作區（此需求中每個容器各自隔離）

**專案資料夾**：使用者提供給遠端 OpenCode 容器作為工作的本機專案檔案集合。
_Avoid_: Git worktree（除非明確指 Git worktree）

**遠端 TUI 工作階段**：使用者透過本機終端與遠端 OpenCode 容器中的互動式文字介面進行的工作階段。
_Avoid_: Web UI（兩者是不同的互動介面）
