# React Vite Features Base

React + Vite + TypeScript 前端基礎專案。使用 HeroUI、Tailwind CSS、Lucide icons、React Router、Zustand 與 Axios。

## 開發環境

- Node.js（建議使用目前 LTS 版本）
- npm

## 開始開發

```bash
npm install
npm run dev
```

Vite 開發伺服器預設使用 <http://localhost:3000>。

常用指令：

```bash
npm run typecheck  # TypeScript 型別檢查
npm run build      # 型別檢查並建立 production build
npm run preview    # 預覽 dist 建置結果
```

## 架構

```text
src/
├── App/                       # App 啟動、全域 provider、Router
│   └── Router/
├── Features/                  # 依路由拆分的功能模組
│   └── Home/
│       ├── Layouts/            # 頁面版面組件
│       └── Pages/              # Router 對應頁面
└── Shared/                    # 跨 Feature 共用能力
    ├── Api/                    # Axios 設定、client、錯誤封裝
    ├── Components/             # 共用 UI 元件
    ├── State/                  # Zustand 共用狀態
    ├── Styles/                 # Tailwind 與全域樣式
    └── Utils/                  # cn() 等共用工具
```

新增路由時，在 `Features/<FeatureName>/` 建立該 Feature 的頁面與版面組件，再到 `App/Router/AppRouter.tsx` 註冊。Feature 專屬邏輯放在 Feature 內；多個 Feature 共用的元件、狀態或 API 才放入 `Shared/`。

TypeScript 檔案及目錄採 PascalCase。`@/` alias 指向 `src/`，例如：

```ts
import { Button } from '@/Shared/Components/Button/Button'
```

## UI 與 className

- UI 元件使用 HeroUI，Icon 使用 `lucide-react`。
- 樣式使用 Tailwind CSS。
- 使用 `cn()` 合併 class 並處理 Tailwind 衝突：

```tsx
import { cn } from '@/Shared/Utils/Cn'

<div className={cn('rounded-lg p-4', className)} />
```

## 共用狀態

Zustand store 放在 `Shared/State/`。範例 `CounterStore`：

```tsx
const count = useCounterStore((state) => state.count)
const increment = useCounterStore((state) => state.increment)
```

## API client

共用 Axios client 位於 `Shared/Api/`：

- `ApiConfig.ts`：base URL、timeout 與預設 headers。
- `ApiClient.ts`：`api.get/post/put/patch/delete` 與原始 `apiClient` instance。
- `ApiError.ts`：統一錯誤分類與資訊。

範例：

```ts
import { api } from '@/Shared/Api/ApiClient'

interface User {
  id: string
  name: string
}

const user = await api.get<User>('/users/1')
```

錯誤會轉成 `ApiError`，`kind` 可能是 `http`、`network`、`timeout`、`cancelled` 或 `unknown`；HTTP 錯誤可讀取 `status`、`code` 與 `data`。

## Runtime 環境參數

前端不將 API URL 綁定在 Vite build-time env。`index.html` 會先載入 `public/runtime-config.js`，之後才載入應用程式。部署時可在啟動靜態網站前產生或替換該檔：

```js
window.__APP_CONFIG__ = {
  API_BASE_URL: 'http://localhost:8000/api',
  API_TIMEOUT: 15000,
  APP_NAME: 'Features Base',
}
```

`API_BASE_URL` 是 Axios 的共用 base URL；若部署時透過反向代理，可設定為相對路徑（例如 `/api`）。`API_TIMEOUT` 單位為毫秒。修改此檔後無需重新執行 Vite build。
