import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { AssistantSidebar } from './AssistantSidebar'

const FIXED_NOW = new Date('2026-08-25T08:00:00Z')

import type { AssistantSessionItem } from '@/api/assistant'

function makeSession(title: string, threadId: string): AssistantSessionItem {
  return {
    thread_id: threadId,
    title,
    last_message_at: null,
    created_at: '2026-08-25T10:00:00Z',
    updated_at: '2026-08-25T10:00:00Z',
  }
}

describe('AssistantSidebar', () => {
  it('filters sessions by keyword', () => {
    render(
      <AssistantSidebar
        sessions={[makeSession('平安银行', 't1'), makeSession('宁德时代', 't2')]}
        activeThreadId={undefined}
        isLoading={false}
        onNewThread={() => {}}
        onSwitchThread={() => {}}
        onDeleteThread={() => Promise.resolve()}
      />,
    )

    expect(screen.getByText('平安银行')).toBeInTheDocument()
    expect(screen.getByText('宁德时代')).toBeInTheDocument()

    const search = screen.getByPlaceholderText('搜索会话')
    fireEvent.change(search, { target: { value: '平安' } })

    expect(screen.getByText('平安银行')).toBeInTheDocument()
    expect(screen.queryByText('宁德时代')).not.toBeInTheDocument()
  })

  it('triggers onNewThread when clicking new session button', () => {
    const onNewThread = vi.fn()
    render(
      <AssistantSidebar
        sessions={[]}
        activeThreadId={undefined}
        isLoading={false}
        onNewThread={onNewThread}
        onSwitchThread={() => {}}
        onDeleteThread={() => Promise.resolve()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /新会话/i }))
    expect(onNewThread).toHaveBeenCalledTimes(1)
  })

  it('groups sessions by date', () => {
    vi.setSystemTime(FIXED_NOW)
    render(
      <AssistantSidebar
        sessions={[
          makeSession('今天', 't1'),
          {
            ...makeSession('昨天', 't2'),
            updated_at: '2026-08-24T10:00:00Z',
          },
          {
            ...makeSession('更早', 't3'),
            updated_at: '2026-08-20T10:00:00Z',
          },
        ]}
        activeThreadId={undefined}
        isLoading={false}
        onNewThread={() => {}}
        onSwitchThread={() => {}}
        onDeleteThread={() => Promise.resolve()}
      />,
    )
    expect(screen.getAllByText('今天')).toHaveLength(2)
    expect(screen.getAllByText('昨天')).toHaveLength(2)
    expect(screen.getAllByText('更早')).toHaveLength(2)
    vi.useRealTimers()
  })
})
