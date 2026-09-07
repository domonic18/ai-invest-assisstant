import { EditOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Spin, Typography } from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'

import type { AssistantSessionItem } from '@/api/assistant'

import { SessionItem } from './ui/SessionItem'

interface AssistantSidebarProps {
  sessions: AssistantSessionItem[]
  activeThreadId: string | undefined
  isLoading: boolean
  width?: number
  onNewThread: () => void
  onSwitchThread: (threadId: string) => void
  onDeleteThread: (threadId: string) => Promise<void>
}

function groupSessions(sessions: AssistantSessionItem[]) {
  const today: AssistantSessionItem[] = []
  const yesterday: AssistantSessionItem[] = []
  const earlier: AssistantSessionItem[] = []

  const now = dayjs().startOf('day')
  const yest = now.subtract(1, 'day')

  for (const session of sessions) {
    const time = session.updated_at
      ? dayjs(session.updated_at)
      : session.created_at
        ? dayjs(session.created_at)
        : null
    if (!time) {
      earlier.push(session)
      continue
    }
    if (time.isAfter(now)) {
      today.push(session)
    } else if (time.isAfter(yest)) {
      yesterday.push(session)
    } else {
      earlier.push(session)
    }
  }

  return { today, yesterday, earlier }
}

export function AssistantSidebar({
  sessions,
  activeThreadId,
  isLoading,
  width = 260,
  onNewThread,
  onSwitchThread,
  onDeleteThread,
}: AssistantSidebarProps) {
  const [keyword, setKeyword] = useState('')

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return sessions
    return sessions.filter((s) => (s.title ?? '').toLowerCase().includes(kw))
  }, [sessions, keyword])

  const { today, yesterday, earlier } = groupSessions(filtered)

  return (
    <div
      className="flex h-full shrink-0 flex-col border-r border-gray-800 bg-[#111318]"
      style={{ width }}
    >
      <div className="p-3">
        <Button
          type="primary"
          block
          icon={<EditOutlined />}
          onClick={onNewThread}
          className="mb-3"
        >
          新会话
        </Button>
        <Input
          prefix={<SearchOutlined className="text-gray-500" />}
          placeholder="搜索会话"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          allowClear
          className="bg-transparent"
        />
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Spin size="small" />
          </div>
        ) : filtered.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={<span className="text-gray-500">暂无会话</span>}
            className="py-8"
          />
        ) : (
          <div className="space-y-4">
            {today.length > 0 && (
              <Section title="今天" sessions={today} activeThreadId={activeThreadId} onSwitch={onSwitchThread} onDelete={onDeleteThread} />
            )}
            {yesterday.length > 0 && (
              <Section title="昨天" sessions={yesterday} activeThreadId={activeThreadId} onSwitch={onSwitchThread} onDelete={onDeleteThread} />
            )}
            {earlier.length > 0 && (
              <Section title="更早" sessions={earlier} activeThreadId={activeThreadId} onSwitch={onSwitchThread} onDelete={onDeleteThread} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface SectionProps {
  title: string
  sessions: AssistantSessionItem[]
  activeThreadId: string | undefined
  onSwitch: (threadId: string) => void
  onDelete: (threadId: string) => Promise<void>
}

function Section({ title, sessions, activeThreadId, onSwitch, onDelete }: SectionProps) {
  return (
    <div>
      <Typography.Text className="mb-1 ml-2 block text-xs font-medium text-gray-500">
        {title}
      </Typography.Text>
      <div className="space-y-0.5">
        {sessions.map((session) => (
          <SessionItem
            key={session.thread_id}
            session={session}
            isActive={session.thread_id === activeThreadId}
            onClick={() => onSwitch(session.thread_id)}
            onDelete={() => onDelete(session.thread_id)}
          />
        ))}
      </div>
    </div>
  )
}
