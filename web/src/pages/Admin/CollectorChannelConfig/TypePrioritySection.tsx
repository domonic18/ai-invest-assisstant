import { Button, Space, Typography } from 'antd'
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

import type { CollectorDataTypeChannel } from '@ai-invest/shared'

import { DATA_TYPE_LABEL } from './constants'
import { PriorityRow } from './PriorityRow'

export interface TypePrioritySectionProps {
  dataType: string
  channels: CollectorDataTypeChannel[]
  dirty: boolean
  saving: boolean
  onChange: (channels: CollectorDataTypeChannel[]) => void
  onSave: () => void
  onDebug: (channel: CollectorDataTypeChannel) => void
}

export function TypePrioritySection({
  dataType,
  channels,
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
        <Typography.Text type="secondary">
          暂未配置渠道，可在渠道列表编辑该渠道「支持的数据类型」后自动加入。
        </Typography.Text>
      )}
    </div>
  )
}
