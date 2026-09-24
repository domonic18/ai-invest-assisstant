/**
 * 任务配置：列表（树形表格，业务分类为目录行）/日历（日/周/月总览）双视图。
 * 编辑弹窗内以单一拖拽列表管理渠道顺序：首位=该任务主渠道（source），
 * 其余为类型级备用降级顺序（collector_channel_data_type，同类型任务共用）。
 */

import { Alert, Card, Form, Input, Modal, Segmented, Select, Switch, message } from 'antd'
import { useMemo, useState } from 'react'

import {
  useAdminTasks,
  useDeleteAdminTask,
  useUpdateAdminTask,
} from '@/hooks/useAdminTasks'
import { useCollectorTaskCatalog } from '@/hooks/useCollectorAdmin'
import { useCollectorChannelConfigs } from '@/hooks/useCollectorChannelConfigs'
import {
  useCollectorDataTypeChannels,
  useReplaceDataTypeChannels,
} from '@/hooks/useCollectorDataTypeChannels'
import { ChannelDebugModal } from '@/pages/Admin/CollectorChannelConfig/ChannelDebugModal'
import type { ChannelDebugTarget } from '@/pages/Admin/CollectorChannelConfig/ChannelDebugModal'
import { TypePrioritySection } from '@/pages/Admin/CollectorChannelConfig/TypePrioritySection'
import type { AdminTask, CollectorDataTypeChannel } from '@ai-invest/shared'

import { getSourceLabel } from '@/utils/collectorTaskLabels'

import { TaskCalendar } from './calendar/TaskCalendar'
import { TaskDetailDrawer } from './TaskDetailDrawer'
import { TaskListView } from './TaskListView'

interface TaskFormValues {
  taskName: string
  taskType: string
  remark?: string
  schedule?: string
  isActive: boolean
}

/** 类型渠道按 priority 升序，任务首选渠道（source，须启用）移到首位。 */
function buildOrderedChannels(
  typeChannels: CollectorDataTypeChannel[],
  preferredSource: string | null | undefined,
): CollectorDataTypeChannel[] {
  const ordered = [...typeChannels]
  if (preferredSource) {
    const idx = ordered.findIndex((ch) => ch.source === preferredSource && ch.isEnabled)
    if (idx > 0) ordered.unshift(...ordered.splice(idx, 1))
  }
  return ordered
}

export function AdminTasks() {
  const [form] = Form.useForm<TaskFormValues>()
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminTask | null>(null)
  const [drawerTask, setDrawerTask] = useState<AdminTask | null>(null)
  const { data: catalog } = useCollectorTaskCatalog()
  const { data: dataTypes } = useCollectorDataTypeChannels()
  const { data: channelConfigs } = useCollectorChannelConfigs()
  const replaceMutation = useReplaceDataTypeChannels()

  // 一页取全（~89 行）：列表前端分页，日历需要全量 cron
  const { data, isLoading } = useAdminTasks({ page: 1, pageSize: 200 })
  const tasks = useMemo(() => data?.items ?? [], [data])
  const updateMutation = useUpdateAdminTask()
  const deleteMutation = useDeleteAdminTask()

  const [dragDraft, setDragDraft] = useState<CollectorDataTypeChannel[] | null>(null)
  const [debugTarget, setDebugTarget] = useState<ChannelDebugTarget | null>(null)

  const taskTypeOptions =
    catalog?.items.map((item) => ({ label: item.label, value: item.name })) ?? []
  const descByTaskType = useMemo(() => {
    const map = new Map<string, string>()
    for (const item of catalog?.items ?? []) map.set(item.name, item.description)
    return map
  }, [catalog])

  const channelsByType = useMemo(() => {
    const map = new Map<string, CollectorDataTypeChannel[]>()
    for (const item of dataTypes ?? []) {
      map.set(item.dataType, [...item.channels].sort((a, b) => a.priority - b.priority))
    }
    return map
  }, [dataTypes])

  const typeChannels = useMemo(
    () => (editing ? (channelsByType.get(editing.taskType) ?? []) : []),
    [channelsByType, editing],
  )
  const draft = useMemo(
    () => buildOrderedChannels(typeChannels, editing?.source),
    [typeChannels, editing],
  )
  const channels = dragDraft ?? draft
  const channelsDirty =
    channels.length !== typeChannels.length ||
    channels.some((ch, i) => ch.channelId !== typeChannels[i]?.channelId)
  const sourceChannel = editing?.source
    ? typeChannels.find((ch) => ch.source === editing.source)
    : undefined
  const sourceUnavailable =
    !!editing?.source && (!sourceChannel || !sourceChannel.isEnabled)

  const openEdit = (task: AdminTask) => {
    setDrawerTask(null)
    setDragDraft(null)
    setEditing(task)
    form.setFieldsValue({
      taskName: task.taskName,
      taskType: task.taskType,
      remark: task.remark ?? undefined,
      schedule: task.schedule || undefined,
      isActive: task.isActive,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: TaskFormValues) => {
    if (!editing) return
    // 运行时首选须是已启用渠道（resolver 只查 enabled），主渠道取首位启用项
    const nextSource = channels.find((ch) => ch.isEnabled)?.source ?? editing.source
    const payload = {
      taskName: values.taskName,
      taskType: values.taskType,
      source: nextSource,
      remark: values.remark?.trim() || null,
      schedule: values.schedule,
      isActive: values.isActive,
    }
    try {
      await updateMutation.mutateAsync({ id: editing.id, data: payload })
      if (channelsDirty) {
        await replaceMutation.mutateAsync({
          dataType: editing.taskType,
          items: channels.map((ch, index) => ({ channelId: ch.channelId, priority: index + 1 })),
        })
      }
      message.success('任务已更新')
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      setDrawerTask(null)
      message.success('任务已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const openDebug = (channel: CollectorDataTypeChannel) => {
    setDebugTarget({
      channelId: channel.channelId,
      channelName: channel.name,
      supportedDataTypes:
        channelConfigs?.find((item) => item.id === channel.channelId)?.supportedDataTypes ?? [],
    })
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Segmented
          value={viewMode}
          onChange={(value) => setViewMode(value as 'list' | 'calendar')}
          options={[
            { value: 'list', label: '列表' },
            { value: 'calendar', label: '日历' },
          ]}
        />
        <span className="text-xs text-[#8a8f98]">
          {viewMode === 'list'
            ? '任务按业务分类分组，点分类行展开/收起；渠道主/备优先级在编辑弹窗内调整'
            : '按日/周/月总览定时分布'}
        </span>
      </div>

      {viewMode === 'calendar' ? (
        <Card variant="borderless">
          <TaskCalendar tasks={tasks} loading={isLoading} onOpenDetail={setDrawerTask} />
        </Card>
      ) : (
        <Card variant="borderless">
          <TaskListView
            tasks={tasks}
            loading={isLoading}
            descByTaskType={descByTaskType}
            channelsByType={channelsByType}
            onEdit={openEdit}
            onOpenDetail={setDrawerTask}
          />
        </Card>
      )}

      <TaskDetailDrawer
        task={drawerTask}
        description={drawerTask ? descByTaskType.get(drawerTask.taskType) : undefined}
        channelsByType={channelsByType}
        onClose={() => setDrawerTask(null)}
        onEdit={openEdit}
        onDelete={handleDelete}
      />

      <Modal
        title="编辑任务"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="taskName" label="任务名称" rules={[{ required: true }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="taskType" label="任务类型" rules={[{ required: true }]}>
            <Select options={taskTypeOptions} disabled={!!editing} />
          </Form.Item>
          <Form.Item
            name="remark"
            label="用途备注"
            tooltip="同一任务类型存在多个调度实例时，用备注区分各实例的采集用途；留空则显示类型默认说明"
          >
            <Input maxLength={200} showCount placeholder="例如：盘中半小时级实时快照（COMEX 黄金等外盘指标）" />
          </Form.Item>
          <Form.Item name="schedule" label="执行时间（Cron 表达式）">
            <Input placeholder="例如：0 16 * * 1-5" />
          </Form.Item>
          <Form.Item name="isActive" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>

        {editing && (
          <div className="mt-2 flex flex-col gap-2">
            <div className="text-xs text-[#8a8f98]">
              首位为该任务的主渠道，其余按序降级备用；备用顺序按任务类型共享，同类型任务共用此配置。
            </div>
            {sourceUnavailable && (
              <Alert
                type="warning"
                showIcon
                message={`首选渠道「${getSourceLabel(editing.source)}」当前不可用（已禁用或未配置该类型），生效主渠道为「${getSourceLabel(channels.find((ch) => ch.isEnabled)?.source)}」`}
              />
            )}
            <TypePrioritySection
              dataType={editing.taskType}
              channels={channels}
              dirty={channelsDirty}
              saving={replaceMutation.isPending}
              hideSave
              onChange={setDragDraft}
              onSave={() => undefined}
              onDebug={openDebug}
            />
          </div>
        )}
      </Modal>

      <ChannelDebugModal
        open={debugTarget !== null}
        target={debugTarget}
        presetDataType={editing?.taskType ?? null}
        onClose={() => setDebugTarget(null)}
      />
    </div>
  )
}
