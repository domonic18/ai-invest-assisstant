import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { CeleryQueuesCard } from './CeleryQueuesCard'

import type { CeleryQueues } from '@ai-invest/shared'

const mockState = vi.hoisted(() => ({
  data: undefined as CeleryQueues | undefined,
  error: null as Error | null,
  refetch: vi.fn(),
}))

vi.mock('@/hooks/useCeleryQueues', () => ({
  useCeleryQueues: () => ({
    data: mockState.data,
    isLoading: false,
    error: mockState.error,
    refetch: mockState.refetch,
    isFetching: false,
  }),
}))

function makeData(overrides?: Partial<CeleryQueues>): CeleryQueues {
  return {
    brokerOk: true,
    checkedAt: '2026-09-24T08:00:00Z',
    queues: [
      {
        name: 'collector.realtime',
        label: '实时队列',
        pendingTotal: 1,
        tasks: [
          {
            key: 'log-1',
            taskType: 'stock-minute',
            label: '股票分钟线',
            state: 'running',
            source: 'sina',
            startedAt: '2026-09-24T07:55:00Z',
            finishedAt: null,
            durationMs: null,
            detail: null,
          },
          {
            key: 'pending-0-cid1',
            taskType: 'stock-minute',
            label: '股票分钟线',
            state: 'pending',
            source: 'sina',
            startedAt: null,
            finishedAt: null,
            durationMs: null,
            detail: null,
          },
        ],
      },
      {
        name: 'collector.batch',
        label: '批量队列',
        pendingTotal: 0,
        tasks: [
          {
            key: 'log-2',
            taskType: 'market-daily-review',
            label: '大盘每日复盘',
            state: 'failed',
            source: 'internal',
            startedAt: '2026-09-24T07:30:00Z',
            finishedAt: '2026-09-24T07:31:00Z',
            durationMs: 61_000,
            detail: 'boom',
          },
        ],
      },
      { name: 'collector.heavy', label: '重载队列', pendingTotal: 0, tasks: [] },
    ],
    ...overrides,
  }
}

describe('CeleryQueuesCard', () => {
  it('renders three queue panels with counts', () => {
    mockState.data = makeData()
    render(<CeleryQueuesCard />)
    expect(screen.getByText('实时队列')).toBeInTheDocument()
    expect(screen.getByText('collector.realtime')).toBeInTheDocument()
    expect(screen.getByText(/执行中 1 · 排队 1/)).toBeInTheDocument()
    expect(screen.getByText('重载队列')).toBeInTheDocument()
    expect(screen.getByText('暂无任务')).toBeInTheDocument()
    expect(screen.queryByText(/^\+\d+$/)).not.toBeInTheDocument()
  })

  it('shows pending overflow badge', () => {
    const queues = makeData().queues.map((q) =>
      q.name === 'collector.realtime' ? { ...q, pendingTotal: 60 } : q,
    )
    mockState.data = makeData({ queues })
    render(<CeleryQueuesCard />)
    expect(screen.getByText('+59')).toBeInTheDocument()
  })

  it('shows broker warning when broker unreachable', () => {
    mockState.data = makeData({ brokerOk: false })
    render(<CeleryQueuesCard />)
    expect(screen.getByText(/Broker 不可达/)).toBeInTheDocument()
  })

  it('tooltip shows failed task label, duration and detail on hover', async () => {
    mockState.data = makeData()
    render(<CeleryQueuesCard />)
    fireEvent.mouseEnter(screen.getByTestId('task-log-2'))
    await waitFor(() => expect(screen.getByText('大盘每日复盘')).toBeInTheDocument())
    expect(screen.getByText(/失败 · internal · 耗时 1m01s/)).toBeInTheDocument()
    expect(screen.getByText('boom')).toBeInTheDocument()
  })

  it('shows error alert with retry when load fails', () => {
    mockState.data = undefined
    mockState.error = new Error('network down')
    render(<CeleryQueuesCard />)
    expect(screen.getByText('队列状态加载失败')).toBeInTheDocument()
    fireEvent.click(screen.getByText(/^重\s*试$/))
    expect(mockState.refetch).toHaveBeenCalled()
  })
})
