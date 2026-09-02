import { AxiosError } from 'axios'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from './client'

function makeResponse(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown = {}
): AxiosResponse {
  return { data, status, statusText: '', headers: {}, config, request: null }
}

/** 依次返回 statuses 中的状态码（逐次抛 AxiosError），耗尽后返回 200 */
function installStatusSequence(statuses: number[]): () => number {
  let call = 0
  const nextStatus = () => {
    const status = call < statuses.length ? statuses[call] : 200
    call += 1
    return status
  }
  apiClient.defaults.adapter = async (config) => {
    const status = nextStatus()
    if (status >= 400) {
      throw new AxiosError(
        'Request failed',
        AxiosError.ERR_BAD_RESPONSE,
        config,
        null,
        makeResponse(config, status)
      )
    }
    return makeResponse(config, status, { ok: true })
  }
  return nextStatus
}

/** 抛网络级错误（无 response），tries 次后返回 200 */
function installNetworkFailureSequence(tries: number): void {
  let call = 0
  apiClient.defaults.adapter = async (config) => {
    call += 1
    if (call <= tries) {
      throw new AxiosError('connect refused', 'ECONNREFUSED', config)
    }
    return makeResponse(config, 200, { ok: true })
  }
}

describe('apiClient 502 容错', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    delete apiClient.defaults.adapter
  })

  it('GET 502 重试后成功', async () => {
    installStatusSequence([502, 502])
    const promise = apiClient.get('/x')
    await vi.runAllTimersAsync()
    const resp = await promise
    expect(resp.status).toBe(200)
  })

  it('GET 网络错误重试后成功', async () => {
    installNetworkFailureSequence(2)
    const promise = apiClient.get('/x')
    await vi.runAllTimersAsync()
    const resp = await promise
    expect(resp.status).toBe(200)
  })

  it('GET 连续 3 次 502 达到重试上限后失败', async () => {
    const nextStatus = installStatusSequence([502, 502, 502])
    const promise = apiClient.get('/x').catch((error) => error)
    await vi.runAllTimersAsync()
    const error = await promise
    expect(error.response.status).toBe(502)
    expect(nextStatus()).toBe(200) // 序列耗尽说明恰好请求了 3 次（1 + 2 重试）
  })

  it('POST 502 不重试', async () => {
    const nextStatus = installStatusSequence([502])
    const promise = apiClient.post('/x').catch((error) => error)
    await vi.runAllTimersAsync()
    const error = await promise
    expect(error.response.status).toBe(502)
    expect(nextStatus()).toBe(200) // 仅 1 次请求
  })

  it('GET 404 不重试', async () => {
    const nextStatus = installStatusSequence([404])
    const promise = apiClient.get('/x').catch((error) => error)
    await vi.runAllTimersAsync()
    const error = await promise
    expect(error.response.status).toBe(404)
    expect(nextStatus()).toBe(200) // 仅 1 次请求
  })

  it('服务端 detail 转为 message 且保留 status', async () => {
    let call = 0
    apiClient.defaults.adapter = async (config) => {
      call += 1
      throw new AxiosError(
        'Request failed',
        AxiosError.ERR_BAD_REQUEST,
        config,
        null,
        makeResponse(config, 400, { detail: '业务错误' })
      )
    }
    const promise = apiClient.get('/x').catch((error) => error)
    const error = await promise
    expect(error.message).toBe('业务错误')
    expect(error.response.status).toBe(400)
    expect(call).toBe(1)
  })
})
