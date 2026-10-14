import { useCallback, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Select, SelectItem } from '@heroui/react'
import type { CommandEnvironment, CreatedContainer, ManagedContainer } from '@/Features/Containers/Api/ContainerApi'
import { containerApi } from '@/Features/Containers/Api/ContainerApi'
import { Button } from '@/Shared/Components/Button/Button'
import { managementErrorMessage } from '@/Features/Containers/Utils/ManagementErrorMessage'
import { ManagementTokenPanel } from '@/Features/Containers/Components/ManagementTokenPanel'

export function ContainerDashboard() {
  const location = useLocation()
  const isCreate = location.pathname === '/containers/create'
  const isCli = location.pathname === '/cli'
  const [token, setToken] = useState('')
  const [containers, setContainers] = useState<ManagedContainer[]>([])
  const [hasLoaded, setHasLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [createdContainer, setCreatedContainer] = useState<CreatedContainer | null>(null)
  const [copyFeedback, setCopyFeedback] = useState('')
  const [commandEnvironments, setCommandEnvironments] = useState<Record<string, CommandEnvironment>>({})
  const [commands, setCommands] = useState<Record<string, { upload: string; connect: string }>>({})
  const [commandLoading, setCommandLoading] = useState<Record<string, boolean>>({})
  const [commandErrors, setCommandErrors] = useState<Record<string, string>>({})
  const [copiedCommand, setCopiedCommand] = useState<{ containerId: string; kind: 'upload' | 'connect' } | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteInProgress, setDeleteInProgress] = useState(false)
  const [deleteSuccess, setDeleteSuccess] = useState('')
  const [cliEnvironment, setCliEnvironment] = useState<CommandEnvironment | ''>('')
  const [cliCommand, setCliCommand] = useState('')
  const [cliLoading, setCliLoading] = useState(false)
  const [cliError, setCliError] = useState('')
  const [cliCopyFeedback, setCliCopyFeedback] = useState('')

  const loadContainers = useCallback(async () => {
    if (!token.trim() || loading) return
    setLoading(true)
    setError('')
    try {
      setContainers(await containerApi.list(token.trim()))
      setHasLoaded(true)
    } catch (cause) {
      setError(managementErrorMessage(cause, '載入容器清單失敗，請稍後重試。'))
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
      setError(managementErrorMessage(cause, '建立容器失敗，請稍後重試。'))
    } finally {
      setCreating(false)
    }
  }

  const copyValue = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopyFeedback(`已複製 ${label}`)
  }

  const loadCommand = async (container: ManagedContainer, environment: CommandEnvironment) => {
    setCommandEnvironments((current) => ({ ...current, [container.id]: environment }))
    setCommandLoading((current) => ({ ...current, [container.id]: true }))
    setCommandErrors((current) => ({ ...current, [container.id]: '' }))
    setCommands((current) => ({ ...current, [container.id]: { upload: '', connect: '' } }))
    setCopiedCommand(null)
    try {
      const result = await containerApi.getCommands(container.id, environment, token.trim())
      const upload = result.upload_command ?? ''
      const connect = result.connect_command ?? ''
      if (upload || connect) setCommands((current) => ({ ...current, [container.id]: { upload, connect } }))
      else setCommandErrors((current) => ({ ...current, [container.id]: '目前無法取得容器上傳與連線指令。' }))
    } catch (cause) {
      setCommandErrors((current) => ({
        ...current,
        [container.id]: managementErrorMessage(cause, '取得容器連線指令失敗，請稍後重試。'),
      }))
    } finally {
      setCommandLoading((current) => ({ ...current, [container.id]: false }))
    }
  }

  const loadCliInstallCommand = async () => {
    if (!token.trim() || !cliEnvironment || cliLoading) return
    setCliLoading(true)
    setCliError('')
    setCliCommand('')
    setCliCopyFeedback('')
    try {
      const result = await containerApi.getCliInstallCommand(cliEnvironment, token.trim())
      setCliCommand(result.command)
    } catch (cause) {
      setCliError(managementErrorMessage(cause, '取得 CLI 安裝命令失敗，請稍後重試。'))
    } finally {
      setCliLoading(false)
    }
  }

  const copyCliInstallCommand = async () => {
    try {
      await navigator.clipboard.writeText(cliCommand)
      setCliCopyFeedback('CLI 安裝命令已複製')
    } catch {
      setCliError('複製 CLI 安裝命令失敗。')
    }
  }

  const copyCommand = async (containerId: string, kind: 'upload' | 'connect') => {
    const command = commands[containerId]?.[kind]
    if (!command) return
    try {
      await navigator.clipboard.writeText(command)
      setCopiedCommand({ containerId, kind })
    } catch {
      const label = kind === 'upload' ? '上傳' : '連線'
      setCommandErrors((current) => ({ ...current, [containerId]: `複製${label}指令失敗。` }))
    }
  }

  const deleteContainer = async () => {
    if (!deletingId || !token.trim() || deleteInProgress) return
    const containerId = deletingId
    setDeleteInProgress(true)
    setDeleteError('')
    setDeleteSuccess('')
    try {
      await containerApi.delete(token.trim(), containerId)
      setContainers((current) => current.filter((container) => container.id !== containerId))
      setDeleteSuccess(`容器 ${containerId} 已刪除。`)
      setDeletingId(null)
    } catch (cause) {
      setDeleteError(managementErrorMessage(cause, `刪除容器 ${containerId} 失敗，請稍後重試。`))
      setDeletingId(null)
    } finally {
      setDeleteInProgress(false)
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-100 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8">
          <p className="text-sm font-semibold text-violet-300">OpenCode 容器管理</p>
          <h1 className="mt-2 text-3xl font-semibold">{isCreate ? '建立容器' : isCli ? 'CLI 工具' : 'OpenCode 容器'}</h1>
          <nav aria-label="Dashboard 分頁" className="mt-6 flex gap-5 border-b border-zinc-800 pb-3">
            <Link className={!isCreate && !isCli ? 'text-violet-300' : 'text-zinc-400'} to="/">容器清單</Link>
            <Link className={isCreate ? 'text-violet-300' : 'text-zinc-400'} to="/containers/create">建立容器</Link>
            <Link className={isCli ? 'text-violet-300' : 'text-zinc-400'} to="/cli">CLI 工具</Link>
          </nav>
        </header>

        <ManagementTokenPanel
          token={token}
          onTokenChange={setToken}
          onLoad={isCreate ? undefined : isCli ? loadCliInstallCommand : loadContainers}
          loadLabel={isCli ? '取得安裝命令' : undefined}
          actionDisabled={isCli && !cliEnvironment}
          loading={isCli ? cliLoading : loading}
          hasLoaded={isCli ? Boolean(cliCommand) : hasLoaded}
        />

        {isCli ? (
          <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-6" aria-label="CLI 工具安裝">
            <h2 className="text-xl font-semibold">下載並安裝 CLI 工具</h2>
            <p className="mt-2 text-sm text-zinc-400">選擇本機作業系統後取得安裝命令；在終端機執行命令即可下載並安裝 CLI。</p>
            <div className="mt-4 max-w-xs">
              <Select
                label="作業系統"
                placeholder="選擇作業系統"
                selectedKeys={cliEnvironment ? [cliEnvironment] : []}
                onSelectionChange={(keys) => {
                  const environment = Array.from(keys)[0] as CommandEnvironment | undefined
                  setCliEnvironment(environment ?? '')
                  setCliCommand('')
                  setCliError('')
                  setCliCopyFeedback('')
                }}
              >
                <SelectItem key="mac">macOS</SelectItem>
                <SelectItem key="windows">Windows</SelectItem>
                <SelectItem key="linux">Linux</SelectItem>
              </Select>
            </div>
            {cliLoading && <p className="mt-3" role="status">正在取得 CLI 安裝命令…</p>}
            {cliError && <p className="mt-3 rounded-lg border border-red-800 bg-red-950/50 p-3 text-red-200" role="alert">{cliError}</p>}
            {cliCommand && (
              <div className="mt-4">
                <code className="block break-all rounded-lg bg-zinc-950 p-3">{cliCommand}</code>
                <Button className="mt-3" variant="bordered" onPress={copyCliInstallCommand}>複製安裝命令</Button>
              </div>
            )}
            {cliCopyFeedback && <p className="mt-2 text-sm text-green-300" role="status">{cliCopyFeedback}</p>}
          </section>
        ) : isCreate ? (
          <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <Button isDisabled={!token.trim() || creating} onPress={createContainer}>{creating ? '建立中…' : '建立 OpenCode 容器'}</Button>
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
                    <Button className="mt-2 text-violet-300 underline" variant="light" onPress={() => void copyValue(label, value)}>複製 {label}</Button>
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
                <Button variant="bordered" isDisabled={!token.trim() || loading} onPress={loadContainers}>
                  {loading && hasLoaded ? '更新中…' : '重新整理'}
                </Button>
              </div>
              {error && <p className="mb-4 rounded-lg border border-red-800 bg-red-950/50 p-3 text-red-200" role="alert">{error}</p>}
              {deleteError && <p className="mb-4 rounded-lg border border-red-800 bg-red-950/50 p-3 text-red-200" role="alert">{deleteError}</p>}
              {deleteSuccess && <p className="mb-4 rounded-lg border border-emerald-800 bg-emerald-950/50 p-3 text-emerald-200" role="status">{deleteSuccess}</p>}
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
                      {container.connect_url && (
                        <div className="mt-4 border-t border-zinc-800 pt-4">
                          <a className="text-violet-300 underline" href={container.connect_url} rel="noopener noreferrer" target="_blank">開啟容器</a>
                          <div className="mt-3 flex flex-wrap items-center gap-3">
                            <label htmlFor={`environment-${container.id}`}>作業系統</label>
                            <Select
                              className="w-48"
                              isDisabled={commandLoading[container.id]}
                              id={`environment-${container.id}`}
                              label="作業系統"
                              placeholder="選擇作業系統"
                              selectedKeys={commandEnvironments[container.id] ? [commandEnvironments[container.id]] : []}
                              onSelectionChange={(keys) => { const environment = Array.from(keys)[0] as CommandEnvironment | undefined; if (environment) void loadCommand(container, environment) }}
                            >
                              <SelectItem key="mac">macOS</SelectItem>
                              <SelectItem key="windows">Windows</SelectItem>
                              <SelectItem key="linux">Linux</SelectItem>
                            </Select>
                          </div>
                          {commandLoading[container.id] && <p className="mt-2" role="status">正在取得連線指令…</p>}
                          {commandErrors[container.id] && <p className="mt-2 text-red-200" role="alert">{commandErrors[container.id]}</p>}
                          {commands[container.id]?.upload && (
                            <div className="mt-3">
                              <p className="mb-2 text-sm text-zinc-400">專案上傳指令</p>
                              <code className="block break-all rounded-lg bg-zinc-950 p-3">{commands[container.id].upload}</code>
                              <Button className="mt-2" variant="bordered" onPress={() => copyCommand(container.id, 'upload')}>複製上傳指令</Button>
                              {copiedCommand?.containerId === container.id && copiedCommand.kind === 'upload' && <p className="mt-2 text-sm text-green-300" role="status">上傳指令已複製</p>}
                            </div>
                          )}
                          {commands[container.id]?.connect && (
                            <div className="mt-3">
                              <p className="mb-2 text-sm text-zinc-400">容器連線指令</p>
                              <code className="block break-all rounded-lg bg-zinc-950 p-3">{commands[container.id].connect}</code>
                              <Button className="mt-2" variant="bordered" onPress={() => copyCommand(container.id, 'connect')}>複製連線指令</Button>
                              {copiedCommand?.containerId === container.id && copiedCommand.kind === 'connect' && <p className="mt-2 text-sm text-green-300" role="status">連線指令已複製</p>}
                            </div>
                          )}
                        </div>
                      )}
                      <Button
                        className="ml-4 text-red-300"
                        isDisabled={deleteInProgress}
                        onPress={() => { setDeleteError(''); setDeletingId(container.id) }}
                        variant="bordered"
                      >
                        刪除容器 {container.id}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              {deletingId && (
                <div aria-label={`確認刪除容器 ${deletingId}`} aria-modal="true" className="fixed inset-0 z-10 flex items-center justify-center bg-black/70 p-6" role="alertdialog">
                  <div className="max-w-lg rounded-xl border border-zinc-700 bg-zinc-900 p-6 shadow-xl">
                    <h2 className="text-xl font-semibold">確認刪除容器 {deletingId}？</h2>
                    <p className="mt-3">刪除會強制停止並移除容器，且永久清除容器工作資料。此操作無法復原。</p>
                    <div className="mt-6 flex justify-end gap-3">
                      <Button variant="bordered" isDisabled={deleteInProgress} onPress={() => setDeletingId(null)}>取消刪除</Button>
                      <Button color="danger" isDisabled={deleteInProgress} onPress={deleteContainer}>{deleteInProgress ? '刪除中…' : '確認刪除'}</Button>
                    </div>
                  </div>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  )
}
