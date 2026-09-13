import { PlusOutlined } from '@ant-design/icons'
import { Button, Space, Tag, Typography } from 'antd'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable'

import type { CollectorChannelConfig, CollectorDataTypeChannel } from '@ai-invest/shared'

import { DATA_TYPE_LABEL } from './constants'
import { PriorityRow } from './PriorityRow'

export interface TypePrioritySectionProps {
  dataType: string
  channels: CollectorDataTypeChannel[]
  allChannels: CollectorChannelConfig[]
  dirty: boolean
  saving: boolean
  onChange: (channels: CollectorDataTypeChannel[]) => void
  onSave: () => void
  onDebug: (channel: CollectorDataTypeChannel) => void
}

export function TypePrioritySection({
  dataType,
  channels,
  allChannels,
  dirty,
  saving,
  onChange,
  onSave,
  onDebug,
}: TypePrioritySectionProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = channels.findIndex((item) => item.channelId === active.id)
    const newIndex = channels.findIndex((item) => item.channelId === over.id)
    if (oldIndex < 0 || newIndex < 0) return
    onChange(arrayMove(channels, oldIndex, newIndex))
  }

  const move = (index: number, offset: number) => {
    const target = index + offset
    if (target < 0 || target >= channels.length) return
    onChange(arrayMove(channels, index, target))
  }

  const remove = (channelId: number) => {
    onChange(channels.filter((item) => item.channelId !== channelId))
  }

  const add = (channelId: number) => {
    const channel = allChannels.find((item) => item.id === channelId)
    if (!channel) return
    onChange([
      ...channels,
      {
        channelId: channel.id,
        source: channel.source,
        name: channel.name,
        isEnabled: channel.isEnabled,
        priority: channels.length + 1,
      },
    ])
  }

  const addableChannels = allChannels.filter(
    (channel) => !channels.some((item) => item.channelId === channel.id),
  )
  const label = DATA_TYPE_LABEL[dataType] || dataType

  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center justify-between">
        <Space size={8}>
          <Typography.Text strong>{label}</Typography.Text>
          {label !== dataType && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {dataType}
            </Typography.Text>
          )}
        </Space>
        <Button size="small" type="primary" disabled={!dirty} loading={saving} onClick={onSave}>
          保存
        </Button>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext
          items={channels.map((item) => item.channelId)}
          strategy={verticalListSortingStrategy}
        >
          {channels.map((channel, index) => (
            <PriorityRow
              key={channel.channelId}
              channel={channel}
              index={index}
              total={channels.length}
              onMove={move}
              onRemove={remove}
              onDebug={onDebug}
            />
          ))}
        </SortableContext>
      </DndContext>
      {channels.length === 0 && (
        <Typography.Text type="secondary">暂未配置渠道，点击下方标签添加。</Typography.Text>
      )}

      {addableChannels.length > 0 && (
        <div className="mt-2">
          <Typography.Text type="secondary" className="mr-2">
            <PlusOutlined /> 添加渠道：
          </Typography.Text>
          <Space size={[0, 8]} wrap>
            {addableChannels.map((channel) => (
              <Tag.CheckableTag
                key={channel.id}
                checked={false}
                onChange={() => add(channel.id)}
                style={{ fontSize: 13, padding: '3px 10px' }}
              >
                {channel.name}
              </Tag.CheckableTag>
            ))}
          </Space>
        </div>
      )}
    </div>
  )
}
