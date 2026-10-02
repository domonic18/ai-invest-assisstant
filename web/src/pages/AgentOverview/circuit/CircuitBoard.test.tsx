import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CircuitBoard } from './CircuitBoard'

import { makeOverviewItem } from '../testFixtures'

const PROPS = {
  selectedKey: null,
  onSelectAgent: () => {},
  systemStatus: undefined,
  celeryQueues: undefined,
  latestOrder: null,
  today: '2026-09-30',
  nowMinutes: 13 * 60 + 45,
  reducedMotion: false,
}

const FIVE_STATES = (['working', 'produced_today', 'off', 'idle', 'paused'] as const).map(
  (runtimeState, i) =>
    makeOverviewItem({
      runtimeState,
      profile: {
        ...makeOverviewItem().profile,
        agentKey: `agent-${i}`,
        name: `Agent${i}`,
        accentColor: ['#22d3ee', '#a855f7', '#8a8f98', '#34d399', '#f59e0b'][i],
      },
      orderCount: i === 0 ? 1 : 0,
      recentActivity:
        i < 2
          ? [{ kind: 'plan' as const, title: '计划生成', occurredAt: '2026-09-30T09:35:00+08:00' }]
          : [],
      nextTasks:
        i === 0 ? [{ task: '复盘', scheduledAt: '2026-09-30T18:35:00+08:00' }] : [],
    }),
)

describe('CircuitBoard', () => {
  it('五态芯片同屏渲染不崩溃，语义丝印/标签齐全', () => {
    render(<CircuitBoard items={FIVE_STATES} {...PROPS} />)
    expect(screen.getByText('RV-ENGINE-01')).toBeInTheDocument()
    expect(screen.getByText('SOCKET EMPTY · NO POWER')).toBeInTheDocument()
    expect(screen.getByText(/RUN · 100% LOAD/)).toBeInTheDocument()
    expect(screen.getByText('逻辑分析仪 · 日内业务时间线')).toBeInTheDocument()
    expect(screen.getByText('NOW 13:45')).toBeInTheDocument()
    expect(screen.getByText('NO CARRIER')).toBeInTheDocument()
  })

  it('板面五态小注：一行式速读（原型图例卡的正式页替代）', () => {
    render(<CircuitBoard items={FIVE_STATES} {...PROPS} />)
    expect(screen.getByText('芯片五态')).toBeInTheDocument()
    expect(screen.getByText('未启用·空槽')).toBeInTheDocument()
    expect(screen.getByText('暂停·门控')).toBeInTheDocument()
  })

  it('reduced-motion：关闭脉冲与动画（ahc-reduced 容器）', () => {
    const { container } = render(<CircuitBoard items={FIVE_STATES} {...PROPS} reducedMotion />)
    expect(container.querySelector('.ahc-reduced')).not.toBeNull()
    expect(container.querySelector('animateMotion')).toBeNull()
  })

  it('点击芯片触发 onSelectAgent', () => {
    let picked = ''
    render(<CircuitBoard items={FIVE_STATES} {...PROPS} onSelectAgent={(key) => (picked = key)} />)
    screen.getByRole('button', { name: 'Agent0' }).dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(picked).toBe('agent-0')
  })

  it('最新委托渲染柜台 ORD 丝印与 LA 红标', () => {
    render(
      <CircuitBoard
        items={FIVE_STATES}
        {...PROPS}
        latestOrder={{ agentKey: 'agent-0', volume: 900, price: 10.98, ackTime: '13:44:58', minutes: 13 * 60 + 44 }}
      />,
    )
    expect(screen.getByText('ORD 900×10.98')).toBeInTheDocument()
    expect(screen.getByText(/13:44:58 委托/)).toBeInTheDocument()
  })
})
