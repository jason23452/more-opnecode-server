import { api } from '@/Shared/Api/ApiClient'

export type ManagedContainer = {
  id: string
  status: 'healthy' | 'unhealthy'
  url: string
  upload_url?: string
  connect_url?: string
}

export const containerApi = {
  list: (token: string) => api.get<ManagedContainer[]>('/opencode/containers', {
    headers: { Authorization: `Bearer ${token}` },
  }),
}
