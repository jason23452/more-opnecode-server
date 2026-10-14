import { ApiError } from '@/Shared/Api/ApiError'

export function managementErrorMessage(cause: unknown, fallback: string): string {
  return cause instanceof ApiError && cause.status === 401
    ? '管理 token 無效，請確認後重試。'
    : fallback
}
