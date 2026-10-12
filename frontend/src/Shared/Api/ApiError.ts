import axios from 'axios'

export type ApiErrorKind = 'http' | 'network' | 'timeout' | 'cancelled' | 'unknown'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  readonly code?: string
  readonly data?: unknown

  constructor({
    message,
    kind,
    status,
    code,
    data,
  }: {
    message: string
    kind: ApiErrorKind
    status?: number
    code?: string
    data?: unknown
  }) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.code = code
    this.data = data
  }
}

export function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (!axios.isAxiosError(error)) {
    return new ApiError({
      message: error instanceof Error ? error.message : '發生未知錯誤',
      kind: 'unknown',
    })
  }

  if (axios.isCancel(error)) {
    return new ApiError({ message: '請求已取消', kind: 'cancelled', code: error.code })
  }

  const response = error.response
  const kind: ApiErrorKind = response
    ? 'http'
    : error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT'
      ? 'timeout'
      : 'network'

  return new ApiError({
    message: response
      ? `API 請求失敗 (${response.status})`
      : kind === 'timeout'
        ? 'API 請求逾時'
        : '無法連線至 API 伺服器',
    kind,
    status: response?.status,
    code: error.code,
    data: response?.data,
  })
}
