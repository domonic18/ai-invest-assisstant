import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAutoCollectKline } from './useAutoCollectKline'

const { mutateAsync } = vi.hoisted(() => ({ mutateAsync: vi.fn() }))

vi.mock('@/hooks/useCollectStockKline', () => ({
  useCollectStockKline: () => ({
    mutateAsync,
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  }),
}))

describe('useAutoCollectKline', () => {
  beforeEach(() => {
    mutateAsync.mockReset()
    mutateAsync.mockResolvedValue(undefined)
  })

  it('缺数据时按 empty 模式补采', async () => {
    renderHook(() => useAutoCollectKline('600519', { ready: true, missing: true }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
    expect(mutateAsync).toHaveBeenCalledWith({ mode: 'empty' })
  })

  it('历史被截断时按 depth 模式补采，并透出 truncated 标志', async () => {
    const { result } = renderHook(() =>
      useAutoCollectKline('600519', {
        ready: true,
        missing: false,
        insufficient: true,
        minHealthyBars: 60,
        firstBarDate: '2026-11-05',
      }),
    )

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
    expect(mutateAsync).toHaveBeenCalledWith({
      mode: 'depth',
      minBars: 60,
      beforeFirstBarDate: '2026-11-05',
    })
    expect(result.current.truncated).toBe(true)
  })

  it('落后最近交易日时按 freshness 模式补采', async () => {
    renderHook(() =>
      useAutoCollectKline('600519', {
        ready: true,
        missing: false,
        lastBarDate: '2020-01-02',
        latestTradeDate: '2020-01-03',
      }),
    )

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
    expect(mutateAsync).toHaveBeenCalledWith({
      mode: 'freshness',
      notBefore: '2020-01-03',
    })
  })

  it('数据齐备时不触发补采', async () => {
    const { result } = renderHook(() =>
      useAutoCollectKline('600519', {
        ready: true,
        missing: false,
        lastBarDate: '2020-01-03',
        latestTradeDate: '2020-01-03',
        insufficient: false,
      }),
    )

    await waitFor(() => expect(result.current.truncated).toBe(false))
    expect(mutateAsync).not.toHaveBeenCalled()
  })
})
