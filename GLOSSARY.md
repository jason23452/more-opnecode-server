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

**容器管理介面**：管理者用來建立、查看、連線至及移除 OpenCode 容器的介面。
_Avoid_: 容器控制台（容易與容器內的 OpenCode 介面混淆）

**容器連線 URL**：指向容器 Tunnel ingress 中連線入口的網址，用於開啟遠端 TUI 工作階段。
_Avoid_: Tunnel URL（指 Tunnel 的基底網址，不一定是連線入口）

**容器連線指令**：使用者在本機 CLI 執行、以連線 token 連至指定 OpenCode 容器的命令。
_Avoid_: 啟動指令（不會啟動或重啟容器）

**管理 token**：管理者呼叫容器管理 API 時使用的驗證憑證。
_Avoid_: 連線 token（用於容器連線，與管理 API 驗證用途不同）

**容器工作資料**：OpenCode 容器執行期間使用的專屬檔案與工作目錄。
_Avoid_: 共用工作區（此需求中每個容器各自隔離）

**專案資料夾**：使用者提供給遠端 OpenCode 容器作為工作的本機專案檔案集合。
_Avoid_: Git worktree（除非明確指 Git worktree）

**Git 專案歷史**：Git 儲存庫中記錄的分支、提交與遠端儲存庫資訊，構成專案版本脈絡。
_Avoid_: 專案檔案（不包含版本脈絡）

**Git 認證憑證**：Git 用來驗證使用者對遠端儲存庫存取權限的資訊，可能授權讀取或推送變更。
_Avoid_: Tunnel token（用途是存取容器 Tunnel，與 Git 儲存庫權限不同）

**Git 推送權限**：使用者將本機或遠端工作目錄中的提交寫入 Git 遠端儲存庫的授權能力。
_Avoid_: 專案上傳權限（只授權將專案資料傳入容器）

**遠端 TUI 工作階段**：使用者透過本機終端與遠端 OpenCode 容器中的互動式文字介面進行的工作階段。
_Avoid_: Web UI（兩者是不同的互動介面）

## 部署與驗證

**正式部署**：將可發布版本的前端與後端服務部署至正式環境，供實際使用者連線使用。
_Avoid_: 本機部署（本機用途與正式環境不同）

**本機整合驗證**：在開發者本機共同啟動前端與後端，以確認兩個服務能整合運作的驗證方式。
_Avoid_: 單元測試（驗證範圍不同）

**服務入口**：使用者連線至部署服務時所使用的對外入口；本專案的正式部署以單一入口提供前端與 API 存取。
_Avoid_: 容器連線 URL（該詞專指 OpenCode 容器的連線入口）
