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

export type CommandEnvironment = 'mac' | 'windows' | 'linux'

export type CliInstallCommand = {
  environment: CommandEnvironment
  command: string
}

export type ContainerCommands = {
  upload_command?: string | null
  connect_command?: string | null
}

export const containerApi = {
  list: (token: string) => api.get<ManagedContainer[]>('/opencode/containers', {
    headers: { Authorization: `Bearer ${token}` },
  }),
  create: (token: string) => api.post<CreatedContainer>('/opencode/containers', undefined, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: 0,
  }),
  getCommands: (containerId: string, environment: CommandEnvironment, token: string) =>
    api.get<ContainerCommands>(`/opencode/containers/${encodeURIComponent(containerId)}`, {
      params: { environment },
      headers: { Authorization: `Bearer ${token}` },
    }),
  getCliInstallCommand: (environment: CommandEnvironment, token: string) =>
    api.get<CliInstallCommand>('/opencode/cli-install-command', {
      params: { environment },
      headers: { Authorization: `Bearer ${token}` },
    }),
  delete: (token: string, containerId: string) => api.delete<void>(`/opencode/containers/${encodeURIComponent(containerId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  }),
}
