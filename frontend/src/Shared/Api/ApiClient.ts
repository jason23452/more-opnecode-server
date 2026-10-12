import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { apiConfig } from '@/Shared/Api/ApiConfig'
import { normalizeApiError } from '@/Shared/Api/ApiError'

export const apiClient = axios.create(apiConfig)

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(normalizeApiError(error)),
)

async function request<TResponse, TBody = unknown>(
  method: NonNullable<AxiosRequestConfig<TBody>['method']>,
  url: string,
  data?: TBody,
  config?: Omit<AxiosRequestConfig<TBody>, 'method' | 'url' | 'data'>,
): Promise<TResponse> {
  try {
    const response: AxiosResponse<TResponse> = await apiClient.request<TResponse, AxiosResponse<TResponse>, TBody>({
      ...config,
      method,
      url,
      data,
    })
    return response.data
  } catch (error) {
    throw normalizeApiError(error)
  }
}

export const api = {
  request,
  get: <TResponse>(url: string, config?: AxiosRequestConfig) =>
    request<TResponse>('get', url, undefined, config),
  post: <TResponse, TBody = unknown>(url: string, data?: TBody, config?: AxiosRequestConfig<TBody>) =>
    request<TResponse, TBody>('post', url, data, config),
  put: <TResponse, TBody = unknown>(url: string, data?: TBody, config?: AxiosRequestConfig<TBody>) =>
    request<TResponse, TBody>('put', url, data, config),
  patch: <TResponse, TBody = unknown>(url: string, data?: TBody, config?: AxiosRequestConfig<TBody>) =>
    request<TResponse, TBody>('patch', url, data, config),
  delete: <TResponse>(url: string, config?: AxiosRequestConfig) =>
    request<TResponse>('delete', url, undefined, config),
}
