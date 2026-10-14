import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MainApp } from '@/App/MainApp'
import { apiClient } from '@/Shared/Api/ApiClient'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  vi.restoreAllMocks()
  apiClient.defaults.timeout = 15_000
  window.localStorage.clear()
  window.sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})
afterAll(() => server.close())

describe('容器管理 Dashboard', () => {
  it('從 CLI 工具分頁取得並複製所選平台的安裝命令', async () => {
    window.history.replaceState({}, '', '/cli')
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    server.use(http.get('*/opencode/cli-install-command', ({ request }) => {
      expect(new URL(request.url).searchParams.get('environment')).toBe('windows')
      expect(request.headers.get('authorization')).toBe('Bearer secret-token')
      return HttpResponse.json({ environment: 'windows', command: 'irm https://example/install.ps1 | iex' })
    }))
    render(<MainApp />)

    expect(await screen.findByRole('heading', { name: 'CLI 工具' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: /作業系統/ }))
    await userEvent.click(await screen.findByRole('option', { name: 'Windows' }))
    await userEvent.click(screen.getByRole('button', { name: '取得安裝命令' }))
    expect(await screen.findByText('irm https://example/install.ps1 | iex')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '複製安裝命令' }))
    expect(writeText).toHaveBeenCalledWith('irm https://example/install.ps1 | iex')
  })

  it('將管理 API 請求送往後端 API 前綴', async () => {
    let requestPath = ''
    server.use(http.get('*/opencode/containers', ({ request }) => {
      requestPath = new URL(request.url).pathname
      return HttpResponse.json([])
    }))
    render(<MainApp />)

    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    expect(await screen.findByText('目前沒有容器')).toBeInTheDocument()
    expect(requestPath).toBe('/api/opencode/containers')
  })

  it('從建立路由直達並透過分頁與瀏覽器歷史切換', async () => {
    window.history.replaceState({}, '', '/containers/create')
    render(<MainApp />)

    expect(await screen.findByRole('heading', { name: '建立容器' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: '容器清單' }))
    expect(await screen.findByRole('heading', { name: 'OpenCode 容器' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')

    window.history.back()
    await waitFor(() => expect(window.location.pathname).toBe('/containers/create'))
    expect(screen.getByRole('heading', { name: '建立容器' })).toBeInTheDocument()
  })

  it('以記憶體管理 token 載入並手動更新健康狀態清單', async () => {
    let requests = 0
    server.use(http.get('*/opencode/containers', ({ request }) => {
      requests += 1
      expect(request.headers.get('authorization')).toBe('Bearer secret-token')
      return HttpResponse.json([
        { id: 'healthy-id', status: 'healthy', url: 'https://healthy.example' },
        { id: 'unhealthy-id', status: 'unhealthy', url: 'https://unhealthy.example' },
      ])
    }))
    render(<MainApp />)

    expect(screen.getByText('請輸入管理 token')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))

    expect(await screen.findByText('healthy-id')).toBeInTheDocument()
    expect(screen.getAllByText('健康', { exact: false })).toHaveLength(2)
    expect(screen.getByText('unhealthy-id')).toBeInTheDocument()
    expect(screen.getAllByText('異常', { exact: false })).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'https://healthy.example' })).toHaveAttribute('href', 'https://healthy.example')
    await userEvent.click(screen.getByRole('button', { name: '重新整理' }))
    await waitFor(() => expect(requests).toBe(2))
    expect(window.localStorage.length).toBe(0)
    expect(window.sessionStorage.length).toBe(0)
    expect(window.location.search).toBe('')
  })

  it('開啟容器連線 URL，並查詢及複製專案上傳與連線指令', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    server.use(
      http.get('*/opencode/containers', () => HttpResponse.json([
        { id: 'container-1', status: 'healthy', url: 'https://tunnel.example', connect_url: 'https://tunnel.example/connect' },
      ])),
      http.get('*/opencode/containers/container-1', ({ request }) => {
        expect(new URL(request.url).searchParams.get('environment')).toBe('windows')
        expect(request.headers.get('authorization')).toBe('Bearer secret-token')
        return HttpResponse.json({
          upload_command: 'opencode-project upload --url https://tunnel.example/upload --token=upload-secret --project .',
          connect_command: 'opencode-project connect --url wss://tunnel.example/connect --token=connect-secret',
        })
      }),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))

    const connectLink = await screen.findByRole('link', { name: '開啟容器' })
    expect(connectLink).toHaveAttribute('href', 'https://tunnel.example/connect')
    expect(connectLink).toHaveAttribute('target', '_blank')
    expect(connectLink).toHaveAttribute('rel', expect.stringContaining('noopener'))
    await userEvent.click(screen.getByRole('button', { name: /作業系統/ }))
    await userEvent.click(await screen.findByRole('option', { name: 'Windows' }))
    expect(await screen.findByText('opencode-project upload --url https://tunnel.example/upload --token=upload-secret --project .')).toBeInTheDocument()
    expect(screen.getByText('opencode-project connect --url wss://tunnel.example/connect --token=connect-secret')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '複製上傳指令' }))
    expect(writeText).toHaveBeenCalledWith('opencode-project upload --url https://tunnel.example/upload --token=upload-secret --project .')
    expect(await screen.findByRole('status')).toHaveTextContent('上傳指令已複製')
    await userEvent.click(screen.getByRole('button', { name: '複製連線指令' }))
    expect(writeText).toHaveBeenCalledWith('opencode-project connect --url wss://tunnel.example/connect --token=connect-secret')
    expect(await screen.findByRole('status')).toHaveTextContent('連線指令已複製')
  })

  it('平台指令查詢顯示載入、一般錯誤及 401，並保留管理 token', async () => {
    let calls = 0
    let finishRequest: (() => void) | undefined
    server.use(
      http.get('*/opencode/containers', () => HttpResponse.json([
        { id: 'container-1', status: 'healthy', url: 'https://tunnel.example', connect_url: 'https://tunnel.example/connect' },
      ])),
      http.get('*/opencode/containers/container-1', async () => {
        calls += 1
        if (calls === 1) {
          await new Promise<void>((resolve) => { finishRequest = resolve })
          return HttpResponse.json({ detail: 'unavailable' }, { status: 500 })
        }
        return HttpResponse.json({ detail: 'invalid token' }, { status: 401 })
      }),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    await screen.findByText('container-1')
    await userEvent.click(screen.getByRole('button', { name: /作業系統/ }))
    await userEvent.click(await screen.findByRole('option', { name: 'macOS' }))
    expect(await screen.findByRole('status')).toHaveTextContent('正在取得連線指令')
    finishRequest?.()
    expect(await screen.findByRole('alert')).toHaveTextContent('取得容器連線指令失敗')
    await userEvent.click(screen.getByRole('button', { name: /作業系統/ }))
    await userEvent.click(await screen.findByRole('option', { name: 'Linux' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('管理 token 無效')
    expect(screen.getByLabelText('管理 token')).toHaveValue('secret-token')
  })

  it('請求進行中顯示載入狀態並避免重複送出', async () => {
    let requests = 0
    let finishRequest: (() => void) | undefined
    server.use(http.get('*/opencode/containers', async () => {
      requests += 1
      await new Promise<void>((resolve) => { finishRequest = resolve })
      return HttpResponse.json([])
    }))
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))

    expect(await screen.findByRole('status')).toHaveTextContent('正在載入容器清單')
    expect(screen.getByRole('button', { name: '載入中…' })).toBeDisabled()
    expect(requests).toBe(1)
    finishRequest?.()
    expect(await screen.findByText('目前沒有容器')).toBeInTheDocument()
  })

  it('顯示空清單、一般錯誤與 401 並保留 token 供修正重試', async () => {
    let calls = 0
    server.use(http.get('*/opencode/containers', () => {
      calls += 1
      if (calls === 1) return HttpResponse.json([], { status: 200 })
      if (calls === 2) return HttpResponse.json({ detail: 'unavailable' }, { status: 500 })
      if (calls === 3) return HttpResponse.json({ detail: 'invalid token' }, { status: 401 })
      return HttpResponse.json([{ id: 'retried-id', status: 'healthy', url: 'https://retry.example' }])
    }))
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'wrong-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    expect(await screen.findByText('目前沒有容器')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重新整理' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('載入容器清單失敗')
    await userEvent.click(screen.getByRole('button', { name: '重新整理' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('管理 token 無效')
    expect(screen.getByLabelText('管理 token')).toHaveValue('wrong-token')
    await userEvent.clear(screen.getByLabelText('管理 token'))
    await userEvent.type(screen.getByLabelText('管理 token'), 'correct-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    expect(await screen.findByText('retried-id')).toBeInTheDocument()
  })

  it('取消刪除確認不送出 DELETE 且保留容器', async () => {
    let deleteRequests = 0
    server.use(
      http.get('*/opencode/containers', () => HttpResponse.json([
        { id: 'keep-me', status: 'healthy', url: 'https://keep.example' },
      ])),
      http.delete('*/opencode/containers/:id', () => {
        deleteRequests += 1
        return new HttpResponse(null, { status: 204 })
      }),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    expect(await screen.findByText('keep-me')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '刪除容器 keep-me' }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent('強制停止並移除容器')
    expect(screen.getByRole('alertdialog')).toHaveTextContent('永久清除容器工作資料')
    await userEvent.click(screen.getByRole('button', { name: '取消刪除' }))

    expect(deleteRequests).toBe(0)
    expect(screen.getByText('keep-me')).toBeInTheDocument()
  })

  it('確認刪除使用 Bearer token、避免重複送出並從清單移除', async () => {
    let deleteRequests = 0
    let finishDelete: (() => void) | undefined
    server.use(
      http.get('*/opencode/containers', () => HttpResponse.json([
        { id: 'remove-me', status: 'healthy', url: 'https://remove.example' },
        { id: 'keep-me', status: 'unhealthy', url: 'https://keep.example' },
      ])),
      http.delete('*/opencode/containers/:id', async ({ request, params }) => {
        deleteRequests += 1
        expect(params.id).toBe('remove-me')
        expect(request.headers.get('authorization')).toBe('Bearer secret-token')
        await new Promise<void>((resolve) => { finishDelete = resolve })
        return new HttpResponse(null, { status: 204 })
      }),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    expect(await screen.findByText('remove-me')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '刪除容器 remove-me' }))
    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))

    expect(await screen.findByRole('button', { name: '刪除中…' })).toBeDisabled()
    expect(deleteRequests).toBe(1)
    finishDelete?.()
    expect(await screen.findByRole('status')).toHaveTextContent('容器 remove-me 已刪除')
    expect(screen.queryByText('remove-me')).not.toBeInTheDocument()
    expect(screen.getByText('keep-me')).toBeInTheDocument()
  })

  it('刪除失敗時保留容器，並對 401 顯示管理 token 無效提示', async () => {
    let status = 500
    server.use(
      http.get('*/opencode/containers', () => HttpResponse.json([
        { id: 'cannot-delete', status: 'healthy', url: 'https://cannot.example' },
      ])),
      http.delete('*/opencode/containers/:id', () => HttpResponse.json({ detail: 'failed' }, { status })),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))
    expect(await screen.findByText('cannot-delete')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '刪除容器 cannot-delete' }))
    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('刪除容器 cannot-delete 失敗')
    expect(screen.getByText('cannot-delete')).toBeInTheDocument()

    status = 401
    await userEvent.click(screen.getByRole('button', { name: '刪除容器 cannot-delete' }))
    await userEvent.click(screen.getByRole('button', { name: '確認刪除' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('管理 token 無效')
    expect(screen.getByLabelText('管理 token')).toHaveValue('secret-token')
    expect(screen.getByText('cannot-delete')).toBeInTheDocument()
  })

  it('建立容器時使用 Bearer token，顯示完整回應並更新容器清單', async () => {
    window.history.replaceState({}, '', '/containers/create')
    apiClient.defaults.timeout = 1
    const apiRequestSpy = vi.spyOn(apiClient, 'request')
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => undefined } })
    let created = false
    let createCalls = 0
    server.use(
      http.post('*/opencode/containers', async ({ request }) => {
        createCalls += 1
        expect(request.headers.get('authorization')).toBe('Bearer create-token')
        expect(await request.text()).toBe('')
        await new Promise((resolve) => setTimeout(resolve, 50))
        created = true
        return HttpResponse.json({
          id: 'new-container',
          url: 'https://tunnel.example',
          upload_url: 'https://tunnel.example/upload',
          connect_url: 'https://tunnel.example/connect',
          upload_token: 'upload-secret',
          connect_token: 'connect-secret',
          cli_install_commands: { macos: 'install-mac', windows_powershell: 'install-windows', linux: 'install-linux' },
          upload_command: 'upload --token upload-secret',
          connect_command: 'connect --token connect-secret',
        })
      }),
      http.get('*/opencode/containers', ({ request }) => {
        expect(request.headers.get('authorization')).toBe('Bearer create-token')
        return HttpResponse.json(created ? [{ id: 'new-container', status: 'healthy', url: 'https://tunnel.example' }] : [])
      }),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'create-token')
    await userEvent.click(screen.getByRole('button', { name: '建立 OpenCode 容器' }))
    expect(apiRequestSpy).toHaveBeenCalledWith(expect.objectContaining({
      method: 'post',
      url: '/opencode/containers',
      timeout: 0,
    }))
    expect(await screen.findByRole('status')).toHaveTextContent('正在建立容器')
    expect(screen.getByRole('button', { name: '建立中…' })).toBeDisabled()
    expect(await screen.findByText(/容器識別碼：new-container/)).toBeInTheDocument()
    for (const value of [
      'https://tunnel.example', 'https://tunnel.example/upload', 'https://tunnel.example/connect',
      'upload-secret', 'connect-secret', 'install-mac', 'install-windows', 'install-linux',
      'upload --token upload-secret', 'connect --token connect-secret',
    ]) expect(screen.getByText(value)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '複製 upload token' }))
    expect(await screen.findByText('已複製 upload token')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: '容器清單' }))
    expect(await screen.findByText('new-container')).toBeInTheDocument()
    expect(createCalls).toBe(1)
  })

  it('建立失敗及 401 顯示錯誤且不呈現建立結果', async () => {
    window.history.replaceState({}, '', '/containers/create')
    let calls = 0
    server.use(http.post('*/opencode/containers', ({ request }) => {
      expect(request.headers.get('authorization')).toBe('Bearer retained-token')
      calls += 1
      return calls === 1
        ? HttpResponse.json({ detail: 'unavailable' }, { status: 500 })
        : HttpResponse.json({ detail: 'invalid token' }, { status: 401 })
    }))
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'retained-token')
    await userEvent.click(screen.getByRole('button', { name: '建立 OpenCode 容器' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('建立容器失敗')
    expect(screen.queryByText('new-container')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '建立 OpenCode 容器' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('管理 token 無效')
    expect(screen.getByLabelText('管理 token')).toHaveValue('retained-token')
  })
})
