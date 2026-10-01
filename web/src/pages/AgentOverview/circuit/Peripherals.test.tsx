import { render } from '@testing-library/react'
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
    startedAt: null,
    finishedAt: null,
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
        makeTask({ key: 'run1', state: 'running', source: 'sina' }),
        ...Array.from({ length: 8 }, (_, i) => makeTask({ key: `ok${i}` })),
      ],
    },
    {
      name: 'collector.heavy',
      label: '重载队列',
      pendingTotal: 0,
      tasks: [
        makeTask({ key: 'fail1', label: 'AI复盘', state: 'failed', detail: '模型未返回结构化输出' }),
        makeTask({ key: 'part1', state: 'partial' }),
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

/** 带悬停详情的任务方框（rect > title），与外设区其它无 title 的 rect 区分。 */
function taskSquareTitles(container: Element): string[] {
  return [...container.querySelectorAll('rect > title')].map((t) => t.textContent ?? '')
}

describe('Peripherals · Celery 任务方框', () => {
  it('按队列分组渲染方框，每队列上限 6，悬停详情含队列/任务/状态', () => {
    const { container } = renderPeripherals(QUEUES)
    const titles = taskSquareTitles(container)
    expect(titles).toHaveLength(8) // 实时 6（截断自 9）+ 重载 2 + 批量空不渲染
    expect(titles.filter((t) => t.startsWith('实时队列'))).toHaveLength(6)
    expect(titles.some((t) => t.includes('实时队列 · K线日更') && t.includes('执行中 · sina'))).toBe(true)
    expect(titles.some((t) => t.includes('AI复盘') && t.includes('失败') && t.includes('模型未返回结构化输出'))).toBe(true)
    expect(container.textContent).toContain('执行中 1 · 异常 2 · 正常 8')
    expect(container.textContent).toContain('积压 ×3')
  })

  it('空任务时显示今日暂无任务留痕', () => {
    const { container } = renderPeripherals({ ...QUEUES, queues: [] })
    expect(container.textContent).toContain('今日暂无任务留痕')
    expect(taskSquareTitles(container)).toHaveLength(0)
  })

  it('状态配色遵循服务状态页语义（失败红/成功绿/执行中青）', () => {
    const { container } = renderPeripherals(QUEUES)
    const squareWith = (predicate: (text: string) => boolean) => {
      const rect = [...container.querySelectorAll('rect > title')].find((t) =>
        predicate(t.textContent ?? ''),
      )?.parentElement
      expect(rect).not.toBeNull()
      return rect
    }
    expect(squareWith((t) => t.includes('失败'))?.getAttribute('fill')).toBe(BOARD.red)
    expect(squareWith((t) => t.includes('已完成'))?.getAttribute('fill')).toBe(BOARD.greenLed)
    const runningSquare = squareWith((t) => t.includes('执行中'))
    expect(runningSquare?.getAttribute('fill')).toBe(BOARD.cyan)
    expect(runningSquare?.getAttribute('class')).toContain('ahc-corebeat')
  })
})
