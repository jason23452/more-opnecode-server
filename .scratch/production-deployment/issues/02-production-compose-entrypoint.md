# 02: 建立前後端正式部署 Compose 與單一服務入口

**What to build:** 維護者可使用正式 Compose 啟動前端與 API 後端，使用者透過綁定部署主機 loopback 的單一服務入口（由主機本機可信服務轉送）存取前端與 API；API 仍能透過部署主機 Docker 管理 OpenCode 容器，正式部署設定可解析並接收部署環境設定。外部 trusted ingress、VPN 與認證設定延後處理。

**Blocked by:** 01: 建立前後端容器映像與本機整合驗證.

**Status:** resolved

- [x] 正式 Compose 可使用 01 建立的前端與 API 後端 production 容器映像啟動服務。
- [x] 前端與 `/api` API 請求可經主機 loopback 綁定的單一服務入口提供，前端以 runtime config 使用同源相對 API 路徑。
- [x] API 後端保有透過同主機 Docker daemon 管理 OpenCode 容器的能力。
- [x] 正式服務所需機密與環境設定由部署環境提供，不需提交機密至 repository；必要憑證未設定時 Compose 會拒絕解析。
- [x] 正式 Compose 可在未提供真實機密值的本機情境下以 throwaway 驗證值解析。
- [x] 正式 Compose 不將 OpenCode 容器或 Cloudflare Quick Tunnel 定義為固定的應用服務。
- [x] 服務入口 host port 僅綁定 loopback；不直接對外公開，供主機本機單一可信服務入口使用。

**Validation:** 正式 Compose 在 Windows Docker 環境完成 config、build、up，並由 loopback 單一入口驗證前端與 API 健康端點；部署腳本行為測試 2 passed。
