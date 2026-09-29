import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { AGENT_STATE_META, StateBadge } from './StateBadge'

describe('StateBadge', () => {
  it('renders paused state with amber pause icon', () => {
    render(<StateBadge state="paused" label="已暂停 · 盘中执行关闭" />)
    expect(screen.getByText('已暂停 · 盘中执行关闭')).toBeInTheDocument()
    expect(AGENT_STATE_META.paused.color).toBe('#faad14')
  })

  it('prefers backend state_label over the default text', () => {
    render(<StateBadge state="working" label="作业中 · 每日选股计划" />)
    expect(screen.getByText('作业中 · 每日选股计划')).toBeInTheDocument()
  })
})
