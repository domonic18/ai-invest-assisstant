import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, ExperimentOutlined, HolderOutlined } from '@ant-design/icons'
import { Button, Popconfirm, Space, Tag, theme } from 'antd'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

import type { CollectorDataTypeChannel } from '@ai-invest/shared'

import { SOURCE_LABEL } from './constants'

export interface PriorityRowProps {
  channel: CollectorDataTypeChannel
  index: number
  total: number
  onMove: (index: number, offset: number) => void
  onRemove: (channelId: number) => void
  onDebug: (channel: CollectorDataTypeChannel) => void
}

export function PriorityRow({
  channel,
  index,
  total,
  onMove,
  onRemove,
  onDebug,
}: PriorityRowProps) {
  const { token } = theme.useToken()
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } =
    useSortable({ id: channel.channelId })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 10 : undefined,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 12px',
        marginBottom: 8,
        borderRadius: token.borderRadiusLG,
        border: `1px solid ${token.colorBorderSecondary}`,
        background: isDragging ? token.colorFillQuaternary : token.colorBgContainer,
        boxShadow: isDragging ? token.boxShadowSecondary : undefined,
        opacity: isDragging ? 0.9 : 1,
      }}
    >
      <Button
        ref={setActivatorNodeRef}
        type="text"
        size="small"
        icon={<HolderOutlined />}
        style={{ cursor: 'grab', touchAction: 'none' }}
        {...attributes}
        {...listeners}
      />

      <span style={{ width: 24, textAlign: 'center', color: token.colorTextSecondary }}>
        {index + 1}
      </span>

      <span className="min-w-0 flex-1 truncate" style={{ fontWeight: 500 }}>
        {channel.name}
      </span>
      <Tag>{SOURCE_LABEL[channel.source] || channel.source}</Tag>
      {channel.isEnabled ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>}

      <Space size={4}>
        <Button
          size="small"
          icon={<ExperimentOutlined />}
          onClick={() => onDebug(channel)}
        >
          测试
        </Button>
        <Button
          size="small"
          icon={<ArrowUpOutlined />}
          disabled={index === 0}
          onClick={() => onMove(index, -1)}
        />
        <Button
          size="small"
          icon={<ArrowDownOutlined />}
          disabled={index === total - 1}
          onClick={() => onMove(index, 1)}
        />
        <Popconfirm title="确认移除？" onConfirm={() => onRemove(channel.channelId)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    </div>
  )
}
