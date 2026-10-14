import { Input } from '@heroui/react'
import { Button } from '@/Shared/Components/Button/Button'

interface ManagementTokenPanelProps {
  token: string
  onTokenChange: (token: string) => void
  onLoad?: () => void
  loadLabel?: string
  actionDisabled?: boolean
  loading: boolean
  hasLoaded: boolean
}

export function ManagementTokenPanel({ token, onTokenChange, onLoad, loadLabel = '載入容器清單', actionDisabled = false, loading, hasLoaded }: ManagementTokenPanelProps) {
  return (
    <section className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mt-2 flex flex-wrap gap-3">
        <Input className="min-w-64 flex-1" classNames={{ inputWrapper: 'bg-zinc-950 border border-zinc-700' }} id="management-token" label="管理 token" labelPlacement="outside" onValueChange={onTokenChange} type="password" value={token} />
        {onLoad && <Button isDisabled={!token.trim() || actionDisabled || loading} onPress={onLoad}>{loading && !hasLoaded ? '載入中…' : loadLabel}</Button>}
      </div>
      {!token && <p className="mt-2 text-sm text-zinc-400">請輸入管理 token</p>}
    </section>
  )
}
