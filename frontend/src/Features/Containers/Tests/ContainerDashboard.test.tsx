import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MainApp } from '@/App/MainApp'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  window.localStorage.clear()
  window.sessionStorage.clear()
  window.history.replaceState({}, '', '/')
})
afterAll(() => server.close())

describe('容器管理 Dashboard', () => {
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

  it('開啟容器連線 URL，並以選定平台查詢及複製連線指令', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    server.use(
      http.get('*/opencode/containers', () => HttpResponse.json([
        { id: 'container-1', status: 'healthy', url: 'https://tunnel.example', connect_url: 'https://tunnel.example/connect' },
      ])),
      http.get('*/opencode/containers/container-1', ({ request }) => {
        expect(new URL(request.url).searchParams.get('environment')).toBe('windows')
        expect(request.headers.get('authorization')).toBe('Bearer secret-token')
        return HttpResponse.json({ connect_command: 'opencode-project connect --url wss://tunnel.example/connect --token=secret' })
      }),
    )
    render(<MainApp />)
    await userEvent.type(screen.getByLabelText('管理 token'), 'secret-token')
    await userEvent.click(screen.getByRole('button', { name: '載入容器清單' }))

    const connectLink = await screen.findByRole('link', { name: '開啟容器' })
    expect(connectLink).toHaveAttribute('href', 'https://tunnel.example/connect')
    expect(connectLink).toHaveAttribute('target', '_blank')
    expect(connectLink).toHaveAttribute('rel', expect.stringContaining('noopener'))
    await userEvent.selectOptions(screen.getByLabelText('作業系統'), 'windows')
    expect(await screen.findByText('opencode-project connect --url wss://tunnel.example/connect --token=secret')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '複製連線指令' }))
    expect(writeText).toHaveBeenCalledWith('opencode-project connect --url wss://tunnel.example/connect --token=secret')
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
    await userEvent.selectOptions(screen.getByLabelText('作業系統'), 'mac')
    expect(await screen.findByRole('status')).toHaveTextContent('正在取得連線指令')
    finishRequest?.()
    expect(await screen.findByRole('alert')).toHaveTextContent('取得容器連線指令失敗')
    await userEvent.selectOptions(screen.getByLabelText('作業系統'), 'linux')
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

  it('以直接進入的建立路由提供建立功能佔位', async () => {
    window.history.replaceState({}, '', '/containers/create')
    render(<MainApp />)
    expect(await screen.findByRole('heading', { name: '建立容器' })).toBeInTheDocument()
    expect(screen.getByText('建立容器功能即將提供')).toBeInTheDocument()
  })
})
