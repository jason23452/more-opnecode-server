import { api } from '@/Shared/Api/ApiClient'

export type ManagedContainer = {
  id: string
  status: 'healthy' | 'unhealthy'
  url: string
  upload_url?: string
  connect_url?: string
}

export type CreatedContainer = {
  id: string
  url: string
  upload_url: string
  upload_token: string
  cli_install_commands: Record<string, string>
  upload_command: string
  connect_url: string
  connect_token: string
  connect_command: string
}

export const containerApi = {
  list: (token: string) => api.get<ManagedContainer[]>('/opencode/containers', {
    headers: { Authorization: `Bearer ${token}` },
  }),
  create: (token: string) => api.post<CreatedContainer>('/opencode/containers', undefined, {
    headers: { Authorization: `Bearer ${token}` },
  }),
}
