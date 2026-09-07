import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import dayjs from 'dayjs'

import { SessionItem } from './SessionItem'

import type { AssistantSessionItem } from '@/api/assistant'

function makeSession(overrides?: Partial<AssistantSessionItem>): AssistantSessionItem {
  return {
    thread_id: 't-1',
    title: '测试会话',
    last_message_at: null,
    created_at: '2026-08-25T10:00:00Z',
    updated_at: '2026-08-25T10:30:00Z',
    ...overrides,
  }
}

describe('SessionItem', () => {
  it('renders title and formatted time', () => {
    render(
      <SessionItem
        session={makeSession()}
        isActive={false}
        onClick={() => {}}
        onDelete={() => {}}
      />,
    )
    expect(screen.getByText('测试会话')).toBeInTheDocument()
    // 组件按本地时区渲染 updated_at（dayjs），断言不能用写死时区的字面量，
    // 否则 CI（UTC）与本地（UTC+8）结果不同；期望值由同一 fixture 独立推导
    expect(screen.getByText(dayjs('2026-08-25T10:30:00Z').format('MM-DD HH:mm'))).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    const onClick = vi.fn()
    render(
      <SessionItem
        session={makeSession()}
        isActive={false}
        onClick={onClick}
        onDelete={() => {}}
      />,
    )
    fireEvent.click(screen.getByText('测试会话'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('confirms and calls onDelete', async () => {
    const onDelete = vi.fn()
    render(
      <SessionItem
        session={makeSession()}
        isActive={false}
        onClick={() => {}}
        onDelete={onDelete}
      />,
    )
    fireEvent.click(screen.getByTitle('删除'))
    const confirmButtons = screen.getAllByText(/删\s*除/)
    fireEvent.click(confirmButtons[confirmButtons.length - 1])
    await waitFor(() => expect(onDelete).toHaveBeenCalledTimes(1))
  })

  it('shows active state', () => {
    render(
      <SessionItem
        session={makeSession()}
        isActive={true}
        onClick={() => {}}
        onDelete={() => {}}
      />,
    )
    expect(screen.getByText('测试会话').closest('[role="button"]')).toHaveClass('bg-blue-600/20')
  })
})
