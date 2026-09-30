import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { makeOverviewItem } from '@/pages/AgentOverview/testFixtures'

import { AgentAvatarSwitcher } from './AgentAvatarSwitcher'

describe('AgentAvatarSwitcher', () => {
  const items = [
    makeOverviewItem(),
    makeOverviewItem({
      profile: {
        ...makeOverviewItem().profile,
        agentKey: 'sentinel',
        name: '防守大师',
        accentColor: '#a855f7',
      },
    }),
  ]

  it('渲染常规助手 + 各 Agent 头像，当前对象标记 aria-pressed', () => {
    render(<AgentAvatarSwitcher current="hunter" items={items} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: '切换到 常规助手' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByRole('button', { name: '短线猎手（当前对话）' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: '切换到 防守大师' })).toBeInTheDocument()
  })

  it('点击头像切换对话对象', () => {
    const onChange = vi.fn()
    render(<AgentAvatarSwitcher current="assistant" items={items} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '切换到 防守大师' }))
    expect(onChange).toHaveBeenCalledWith('sentinel')
  })

  it('disabled Agent 不出现头像', () => {
    render(
      <AgentAvatarSwitcher
        current="assistant"
        items={[
          makeOverviewItem({
            profile: { ...makeOverviewItem().profile, agentKey: 'old', status: 'disabled' },
          }),
        ]}
        onChange={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: /短线猎手/ })).not.toBeInTheDocument()
  })
})
