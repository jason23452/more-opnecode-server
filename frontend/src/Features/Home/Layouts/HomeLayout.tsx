import { ArrowUpRight, Blocks, Code2, Layers3, Sparkles } from 'lucide-react'
import { Button } from '@/Shared/Components/Button/Button'
import { useCounterStore } from '@/Shared/State/CounterStore'

const capabilities = [
  { icon: Layers3, title: '三層式架構', description: 'App、Features、Shared 分層，讓頁面與共用能力各就各位。' },
  { icon: Blocks, title: 'Feature 導向路由', description: '每個 Router 對應一個 Feature，版面組件再組合共用元件。' },
  { icon: Code2, title: 'TypeScript 優先', description: '以嚴格型別設定作為新功能的預設開發體驗。' },
]

export function HomeLayout() {
  const count = useCounterStore((state) => state.count)
  const increment = useCounterStore((state) => state.increment)

  return (
    <main className="min-h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8 sm:px-10">
        <header className="flex items-center gap-3 text-sm font-semibold tracking-wide text-zinc-200">
          <span className="grid size-9 place-items-center rounded-xl bg-violet-500/15 text-violet-300"><Sparkles size={18} /></span>
          {window.__APP_CONFIG__?.APP_NAME ?? 'Features Base'}
        </header>

        <section className="grid flex-1 items-center gap-14 py-16 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300">
              <span className="size-1.5 rounded-full bg-emerald-400" /> React · Vite · TypeScript
            </p>
            <h1 className="max-w-2xl text-5xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
              從清晰架構，<span className="text-violet-300">開始打造。</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-zinc-400">
              一套以 Feature 為核心的前端起始專案。共用 UI、狀態與 API 集中管理，讓每個功能保持獨立且容易擴充。
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Button onPress={increment} endContent={<ArrowUpRight size={16} />}>
                Zustand 計數：{count}
              </Button>
              <span className="text-sm text-zinc-500">點擊按鈕測試共用狀態</span>
            </div>
          </div>

          <div className="grid gap-3">
            {capabilities.map(({ icon: Icon, title, description }, index) => (
              <article key={title} className="flex gap-4 rounded-2xl border border-zinc-800/80 bg-zinc-900/65 p-5 shadow-xl shadow-black/10">
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-zinc-800 text-violet-300"><Icon size={20} /></span>
                <div>
                  <p className="text-xs font-medium text-zinc-500">0{index + 1}</p>
                  <h2 className="mt-1 font-medium text-zinc-100">{title}</h2>
                  <p className="mt-1.5 text-sm leading-6 text-zinc-400">{description}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <footer className="border-t border-zinc-800/80 py-5 text-xs text-zinc-500">
          Runtime API：{window.__APP_CONFIG__?.API_BASE_URL || '尚未設定'}
        </footer>
      </div>
    </main>
  )
}
