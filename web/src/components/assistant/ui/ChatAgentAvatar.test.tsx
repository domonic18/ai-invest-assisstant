import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { makeOverviewItem } from '@/pages/AgentOverview/testFixtures'

import { ChatAgentAvatar } from './ChatAgentAvatar'

describe('ChatAgentAvatar', () => {
  it('常规助手渲染助手头像图片', () => {
    const { container } = render(<ChatAgentAvatar agentType="assistant" items={[]} />)
    expect(container.querySelector('img')).toBeTruthy()
  })

  it('已登记 promptId 的交易 Agent 渲染原型头像', () => {
    const items = [
      makeOverviewItem({
        profile: { ...makeOverviewItem().profile, promptId: 'trading_agent_short_line' },
      }),
    ]
    const { container } = render(<ChatAgentAvatar agentType="hunter" items={items} />)
    expect(container.querySelector('img')).toBeTruthy()
    expect(screen.queryByText('短')).not.toBeInTheDocument()
  })

  it('未登记 promptId 回落 accentColor + 名称首字方块', () => {
    const items = [makeOverviewItem()]
    const { container } = render(<ChatAgentAvatar agentType="hunter" items={items} />)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('短')).toBeInTheDocument()
    expect(screen.getByText('短')).toHaveStyle({ color: '#22d3ee' })
  })

  it('agentKey 不在概要清单时按 key 首字回落，不抛错', () => {
    const { container } = render(<ChatAgentAvatar agentType="ghost" items={[]} />)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('g')).toBeInTheDocument()
  })
})
