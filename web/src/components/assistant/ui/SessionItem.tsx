import { DeleteOutlined, MessageOutlined } from '@ant-design/icons'
import { Button, Popconfirm, Typography } from 'antd'
import dayjs from 'dayjs'

import type { AssistantSessionItem } from '@/api/assistant'

interface SessionItemProps {
  session: AssistantSessionItem
  isActive: boolean
  onClick: () => void
  onDelete: () => void
}

export function SessionItem({ session, isActive, onClick, onDelete }: SessionItemProps) {
  const title = session.title?.trim() || '新会话'
  const updatedAt = session.updated_at
    ? dayjs(session.updated_at).format('MM-DD HH:mm')
    : null

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      className={`
        group flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-left
        transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50
        ${isActive ? 'bg-blue-600/20 text-blue-100' : 'text-gray-300 hover:bg-white/5'}
      `}
    >
      <MessageOutlined className="shrink-0 text-xs text-gray-500" />
      <div className="min-w-0 flex-1">
        <Typography.Text
          ellipsis
          className={`block text-sm ${isActive ? 'text-blue-100' : 'text-gray-200'}`}
        >
          {title}
        </Typography.Text>
        {updatedAt && (
          <span className="text-xs text-gray-500">{updatedAt}</span>
        )}
      </div>
      <Popconfirm
        title="删除该会话？"
        onConfirm={(e) => {
          e?.stopPropagation()
          onDelete()
        }}
        onCancel={(e) => e?.stopPropagation()}
        okText="删除"
        cancelText="取消"
        placement="bottomRight"
      >
        <Button
          type="text"
          size="small"
          danger
          icon={<DeleteOutlined />}
          title="删除"
          onClick={(e) => e.stopPropagation()}
          className="opacity-0 transition-opacity group-hover:opacity-100"
        />
      </Popconfirm>
    </div>
  )
}
