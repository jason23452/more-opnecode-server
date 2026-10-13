import { useCallback, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import type { CreatedContainer, ManagedContainer } from '@/Features/Containers/Api/ContainerApi'
import { containerApi } from '@/Features/Containers/Api/ContainerApi'
import { ApiError } from '@/Shared/Api/ApiError'

export function ContainerDashboard() {
  const location = useLocation()
  const isCreate = location.pathname === '/containers/create'
  const [token, setToken] = useState('')
  const [containers, setContainers] = useState<ManagedContainer[]>([])
  const [hasLoaded, setHasLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [createdContainer, setCreatedContainer] = useState<CreatedContainer | null>(null)
  const [copyFeedback, setCopyFeedback] = useState('')

  const loadContainers = useCallback(async () => {
    if (!token.trim() || loading) return
    setLoading(true)
    setError('')
    try {
      setContainers(await containerApi.list(token.trim()))
      setHasLoaded(true)
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : undefined
      setError(status === 401 ? '管理 token 無效，請確認後重試。' : '載入容器清單失敗，請稍後重試。')
    } finally {
      setLoading(false)
    }
  }, [loading, token])

  const createContainer = async () => {
    if (!token.trim() || creating) return
    setCreating(true)
    setError('')
    setCreatedContainer(null)
    try {
      const result = await containerApi.create(token.trim())
      setCreatedContainer(result)
      try {
        setContainers(await containerApi.list(token.trim()))
        setHasLoaded(true)
      } catch {
        setError('容器已建立，但更新容器清單失敗；請返回清單重新整理。')
      }
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : undefined
      setError(status === 401 ? '管理 token 無效，請確認後重試。' : '建立容器失敗，請稍後重試。')
    } finally {
      setCreating(false)
    }
  }

  const copyValue = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopyFeedback(`已複製 ${label}`)
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-100 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8">
          <p className="text-sm font-semibold text-violet-300">OpenCode 容器管理</p>
          <h1 className="mt-2 text-3xl font-semibold">{isCreate ? '建立容器' : 'OpenCode 容器'}</h1>
          <nav aria-label="Dashboard 分頁" className="mt-6 flex gap-5 border-b border-zinc-800 pb-3">
            <Link className={!isCreate ? 'text-violet-300' : 'text-zinc-400'} to="/">容器清單</Link>
            <Link className={isCreate ? 'text-violet-300' : 'text-zinc-400'} to="/containers/create">建立容器</Link>
          </nav>
        </header>

        <section className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <label className="block text-sm font-medium" htmlFor="management-token">管理 token</label>
          <div className="mt-2 flex flex-wrap gap-3">
            <input className="min-w-64 flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2" id="management-token" onChange={(event) => setToken(event.target.value)} type="password" value={token} />
            {!isCreate && <button className="rounded-lg bg-violet-600 px-4 py-2 disabled:opacity-50" disabled={!token.trim() || loading} onClick={loadContainers}>{loading && !hasLoaded ? '載入中…' : '載入容器清單'}</button>}
          </div>
          {!token && <p className="mt-2 text-sm text-zinc-400">請輸入管理 token</p>}
        </section>

        {isCreate ? (
          <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <button className="rounded-lg bg-violet-600 px-4 py-2 disabled:opacity-50" disabled={!token.trim() || creating} onClick={createContainer}>{creating ? '建立中…' : '建立 OpenCode 容器'}</button>
            {creating && <p className="mt-3" role="status">正在建立容器…</p>}
            {error && <p className="mt-3 rounded-lg border border-red-800 bg-red-950/50 p-3 text-red-200" role="alert">{error}</p>}
            {createdContainer && (
              <div className="mt-6 space-y-4" aria-label="建立結果">
                <h2 className="text-xl font-semibold">容器建立成功</h2>
                <p>容器識別碼：{createdContainer.id}</p>
                {[
                  ['Tunnel URL', createdContainer.url], ['upload URL', createdContainer.upload_url],
                  ['connect URL', createdContainer.connect_url], ['upload token', createdContainer.upload_token],
                  ['connect token', createdContainer.connect_token], ['upload 命令', createdContainer.upload_command],
                  ['connect 命令', createdContainer.connect_command],
                  ...Object.entries(createdContainer.cli_install_commands).map(([platform, command]) => [`${platform} 安裝命令`, command]),
                ].map(([label, value]) => (
                  <div className="break-all rounded-lg border border-zinc-800 p-3" key={label}>
                    <p className="text-sm text-zinc-400">{label}</p><p>{value}</p>
                    <button className="mt-2 text-violet-300 underline" onClick={() => void copyValue(label, value)}>複製 {label}</button>
                  </div>
                ))}
                {copyFeedback && <p role="status">{copyFeedback}</p>}
                <Link className="inline-block text-violet-300 underline" to="/">前往容器清單</Link>
              </div>
            )}
          </section>
        ) : (
          <>
            <section aria-label="容器清單">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl font-semibold">容器清單</h2>
                <button className="rounded-lg border border-zinc-700 px-4 py-2 disabled:opacity-50" disabled={!token.trim() || loading} onClick={loadContainers}>
                  {loading && hasLoaded ? '更新中…' : '重新整理'}
                </button>
              </div>
              {error && <p className="mb-4 rounded-lg border border-red-800 bg-red-950/50 p-3 text-red-200" role="alert">{error}</p>}
              {loading && !hasLoaded && <p role="status">正在載入容器清單…</p>}
              {!loading && hasLoaded && containers.length === 0 && (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
                  <p>目前沒有容器</p>
                  <Link className="mt-3 inline-block text-violet-300" to="/containers/create">建立第一個容器</Link>
                </div>
              )}
              {containers.length > 0 && (
                <ul className="grid gap-3">
                  {containers.map((container) => (
                    <li className="rounded-xl border border-zinc-800 bg-zinc-900 p-5" key={container.id}>
                      <p className="font-medium">{container.id}</p>
                      <p className="mt-2 text-sm">健康狀態：{container.status === 'healthy' ? '健康' : '異常'}</p>
                      <a className="mt-2 inline-block break-all text-violet-300 underline" href={container.url} rel="noreferrer" target="_blank">{container.url}</a>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  )
}
