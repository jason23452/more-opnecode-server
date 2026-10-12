import type { AxiosRequestConfig } from 'axios'

export const apiConfig: AxiosRequestConfig = {
  baseURL: window.__APP_CONFIG__?.API_BASE_URL ?? '',
  timeout: window.__APP_CONFIG__?.API_TIMEOUT ?? 15_000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
}
