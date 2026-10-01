import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CeleryQueues, CeleryTaskSquare } from '@ai-invest/shared'

import { Peripherals } from './Peripherals'

import { BOARD } from './boardTheme'

function makeTask(overrides: Partial<CeleryTaskSquare>): CeleryTaskSquare {
  return {
    key: 't',
    taskType: 'kline_stock_daily',
    label: 'K线日更',
    state: 'success',
    source: null,
    startedAt: '2026-10-01T09:30:00+08:00',
    finishedAt: '2026-10-01T09:30:05+08:00',
    durationMs: null,
    detail: null,
    ...overrides,
  }
}

const QUEUES: CeleryQueues = {
  brokerOk: true,
  checkedAt: '2026-10-01T10:00:00+08:00',
  queues: [
    {
      name: 'collector.realtime',
      label: '实时队列',
      pendingTotal: 3,
      tasks: [
        makeTask({ key: 'run1', state: 'running', source: 'sina', finishedAt: null }),
        ...Array.from({ length: 8 }, (_, i) => makeTask({ key: `ok${i}` })),
      ],
    },
    {
      name: 'collector.heavy',
      label: '重载队列',
      pendingTotal: 0,
      tasks: [
        makeTask({
          key: 'fail1',
          label: 'AI复盘',
          state: 'failed',
          detail: '模型未返回结构化输出',
          durationMs: 61_000,
        }),
        makeTask({ key: 'part1', state: 'partial' }),
        makeTask({ key: 'skip1', label: 'AI复盘', state: 'skipped', detail: '输入未就绪' }),
      ],
    },
    { name: 'collector.batch', label: '批量队列', pendingTotal: 0, tasks: [] },
  ],
}

function renderPeripherals(queues?: CeleryQueues) {
  return render(
    <svg>
      <Peripherals
        systemStatus={undefined}
        celeryQueues={queues}
        latestOrder={null}
        today="2026-10-01"
        reducedMotion
      />
    </svg>,
  )
}

/** 任务方框（9×9 描边方块，排除空槽位虚线框），顺序=队列分组渲染序。 */
function taskSquares(container: Element): HTMLElement[] {
  return ([...container.querySelectorAll('rect[height="9"]')] as HTMLElement[]).filter(
    (r) => r.getAttribute('fill') !== 'none',
  )
}

/** 无任务队列的虚线空槽位。 */
function emptySlots(container: Element): HTMLElement[] {
  return [...container.querySelectorAll('rect[stroke-dasharray]')] as HTMLElement[]
}

describe('Peripherals · Celery 任务方框', () => {
  it('按队列分组渲染方框，每队列上限 5，悬停弹出与服务状态页相同的任务详情', async () => {
    const { container } = renderPeripherals(QUEUES)
    const squares = taskSquares(container)
    expect(squares).toHaveLength(8) // 实时 5（截断自 9）+ 重载 3 + 批量空（空槽位不计）

    // running 方框：任务名 + 状态·来源
    fireEvent.mouseEnter(squares[0])
    expect(await screen.findByText('K线日更')).toBeInTheDocument()
    expect(screen.getByText('执行中 · sina')).toBeInTheDocument()

    // failed 方框：耗时 + 详情（antd 关闭有延迟，直接轮询新弹层内容）
    fireEvent.mouseLeave(squares[0])
    fireEvent.mouseEnter(squares[5])
    expect(await screen.findByText('AI复盘')).toBeInTheDocument()
    expect(screen.getByText('失败 · 耗时 1m01s')).toBeInTheDocument()
    expect(screen.getByText('模型未返回结构化输出')).toBeInTheDocument()

    expect(container.textContent).toContain('执行中 1 · 异常 2 · 正常 8')
    expect(container.textContent).toContain('积压 ×3')
    // 三队列恒驻：批量队列今日无任务 → RT/BA/HV 标签齐全 + 批量画空槽位（位于实时组之后）
    expect(emptySlots(container)).toHaveLength(1)
    expect(emptySlots(container)[0].getAttribute('x')).toBe(String(392 + 85 + 17))
  })

  it('只统计今日任务：隔日留痕不入方框与汇总，跳过数入汇总行', async () => {
    const yesterdayOnly: CeleryQueues = {
      ...QUEUES,
      queues: [
        {
          name: 'collector.heavy',
          label: '重载队列',
          pendingTotal: 0,
          tasks: [
            makeTask({
              key: 'old-ok',
              startedAt: '2026-09-30T09:30:00+08:00',
              finishedAt: '2026-09-30T09:30:05+08:00',
            }),
            makeTask({ key: 'today-skip', state: 'skipped' }),
          ],
        },
      ],
    }
    const { container } = renderPeripherals(yesterdayOnly)
    const squares = taskSquares(container)
    expect(squares).toHaveLength(1)
    fireEvent.mouseEnter(squares[0])
    expect(await screen.findByText('已跳过')).toBeInTheDocument()
    expect(container.textContent).toContain('跳过 1')
    expect(container.textContent).not.toContain('正常 1')
  })

  it('running 无 finishedAt 时按 startedAt 归入今日', () => {
    const runningNow: CeleryQueues = {
      ...QUEUES,
      queues: [
        {
          name: 'collector.realtime',
          label: '实时队列',
          pendingTotal: 0,
          tasks: [
            makeTask({ key: 'live', state: 'running', startedAt: '2026-10-01T09:59:00+08:00', finishedAt: null }),
          ],
        },
      ],
    }
    const { container } = renderPeripherals(runningNow)
    expect(taskSquares(container)).toHaveLength(1)
    expect(container.textContent).toContain('执行中 1')
  })

  it('三队列恒驻：无数据/无任务时画 3 个空槽位，悬停提示队列今日无任务', async () => {
    const { container } = renderPeripherals({ ...QUEUES, queues: [] })
    expect(container.textContent).toContain('今日暂无任务留痕')
    expect(taskSquares(container)).toHaveLength(0)
    expect(emptySlots(container)).toHaveLength(3)
    // 悬停空槽位提示所属队列
    fireEvent.mouseEnter(emptySlots(container)[2])
    expect(await screen.findByText('「重载队列」今日无任务留痕')).toBeInTheDocument()

    const noData = renderPeripherals()
    expect(emptySlots(noData.container)).toHaveLength(3)
    expect(noData.container.textContent).toContain('今日暂无任务留痕')
  })

  it('状态配色遵循服务状态页语义（失败红/成功绿/执行中青/跳过淡灰描边）', () => {
    const { container } = renderPeripherals(QUEUES)
    const squares = taskSquares(container)
    // 实时: [running, ok×4] → 重载: [failed, partial, skipped]
    expect(squares[0].getAttribute('fill')).toBe(BOARD.cyan)
    expect(squares[0].getAttribute('class')).toContain('ahc-corebeat')
    expect(squares[1].getAttribute('fill')).toBe(BOARD.greenLed)
    expect(squares[5].getAttribute('fill')).toBe(BOARD.red)
    expect(squares[7].getAttribute('fill')).toBe(BOARD.grey)
    expect(squares[7].getAttribute('fill-opacity')).toBe('0.4')
    expect(squares[7].getAttribute('stroke')).toBe(BOARD.grey)
  })
})
