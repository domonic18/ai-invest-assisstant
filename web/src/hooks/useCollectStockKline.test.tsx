import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import type { StockKline } from '@ai-invest/shared'

import { runCollectorTask } from '@/api/collectorAdmin'
import { fetchStockKline } from '@/api/stocks'

import { useCollectStockKline } from './useCollectStockKline'

vi.mock('@/api/collectorAdmin', () => ({ runCollectorTask: vi.fn() }))
vi.mock('@/api/stocks', () => ({ fetchStockKline: vi.fn() }))

const isoDates = (count: number, startDay = 1): string[] =>
  Array.from(
    { length: count },
    (_, i) => `2026-01-${String(startDay + i).padStart(2, '0')}`,
  )

const klineOf = (dates: string[]) =>
  ({
    code: '600519',
    name: '贵州茅台',
    period: 'daily',
    latestTradeDate: dates[dates.length - 1] ?? '',
    needsBackfill: false,
    minHealthyBars: 60,
    bars: dates.map((date) => ({
      date,
      open: 1,
      high: 1,
      low: 1,
      close: 1,
      volume: 1,
      amount: 1,
      changePct: null,
      amplitude: null,
      turnoverRate: null,
    })),
  }) as unknown as StockKline

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

/** 让 mutationFn 的微任务链跑完并注册轮询定时器，再推进虚拟时钟。 */
const advance = async (ms: number) => {
  await vi.advanceTimersByTimeAsync(0)
  await vi.advanceTimersByTimeAsync(ms)
}

describe('useCollectStockKline', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(runCollectorTask).mockResolvedValue({} as never)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('depth 模式：bar 数达到阈值即达标', async () => {
    vi.mocked(fetchStockKline).mockResolvedValue(klineOf(isoDates(60)))

    const { result } = renderHook(() => useCollectStockKline('600519'), { wrapper })
    const promise = result.current.mutateAsync({
      mode: 'depth',
      minBars: 60,
      beforeFirstBarDate: '2026-02-01',
    })
    await advance(3_100)
    await expect(promise).resolves.toBeUndefined()
    expect(runCollectorTask).toHaveBeenCalledWith('kline', {
      symbols: ['600519'],
      period: 'daily',
    })
  })

  it('depth 模式：历史起点前移即达标（bar 数仍不足阈值）', async () => {
    vi.mocked(fetchStockKline).mockResolvedValue(klineOf(isoDates(6)))

    const { result } = renderHook(() => useCollectStockKline('600519'), { wrapper })
    const promise = result.current.mutateAsync({
      mode: 'depth',
      minBars: 60,
      beforeFirstBarDate: '2026-02-01',
    })
    await advance(3_100)
    await expect(promise).resolves.toBeUndefined()
  })

  it('depth 模式：历史既未补足也未前移则超时失败', async () => {
    vi.mocked(fetchStockKline).mockResolvedValue(klineOf(isoDates(6, 25)))

    const { result } = renderHook(() => useCollectStockKline('600519'), { wrapper })
    const promise = result.current.mutateAsync({
      mode: 'depth',
      minBars: 60,
      beforeFirstBarDate: '2026-01-20',
    })
    const assertion = expect(promise).rejects.toThrow('采集超时')
    await advance(95_000)
    await assertion
  })

  it('empty 模式：出现任意一根 bar 即达标', async () => {
    vi.mocked(fetchStockKline).mockResolvedValue(klineOf(isoDates(1)))

    const { result } = renderHook(() => useCollectStockKline('600519'), { wrapper })
    const promise = result.current.mutateAsync({ mode: 'empty' })
    await advance(3_100)
    await expect(promise).resolves.toBeUndefined()
  })

  it('freshness 模式：末根 bar 不早于期望日才达标', async () => {
    vi.mocked(fetchStockKline).mockResolvedValue(klineOf(isoDates(3)))

    const { result } = renderHook(() => useCollectStockKline('600519'), { wrapper })
    const promise = result.current.mutateAsync({
      mode: 'freshness',
      notBefore: '2026-01-10',
    })
    const assertion = expect(promise).rejects.toThrow('采集超时')
    await advance(95_000)
    await assertion
  })
})
