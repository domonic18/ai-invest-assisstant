/** 任务配置：列表（默认）与日历（日/周/月总览定时分布）双视图 + 编辑表单。 */

import { Card, Form, Input, Modal, Segmented, Select, Switch, message } from 'antd'
import { useMemo, useState } from 'react'

import { useCollectorTaskCatalog } from '@/hooks/useCollectorAdmin'
import {
  useAdminTasks,
  useDeleteAdminTask,
  useUpdateAdminTask,
} from '@/hooks/useAdminTasks'
import { COLLECTOR_TASK_LABEL } from '@/utils/collectorTaskLabels'
import type { AdminTask } from '@ai-invest/shared'

import { TaskCalendar } from './calendar/TaskCalendar'
import { TaskDetailDrawer } from './TaskDetailDrawer'
import { TaskListView } from './TaskListView'

interface TaskFormValues {
  taskName: string
  taskType: string
  source: string
  schedule?: string
  isActive: boolean
}

const FALLBACK_TASK_TYPE_OPTIONS = Object.entries(COLLECTOR_TASK_LABEL).map(([value, label]) => ({
  label,
  value,
}))

export function AdminTasks() {
  const [form] = Form.useForm<TaskFormValues>()
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminTask | null>(null)
  const [drawerTask, setDrawerTask] = useState<AdminTask | null>(null)
  const { data: catalog } = useCollectorTaskCatalog()

  // 一页取全（~89 行）：列表前端分页，日历需要全量 cron
  const { data, isLoading } = useAdminTasks({ page: 1, pageSize: 200 })
  const tasks = useMemo(() => data?.items ?? [], [data])
  const updateMutation = useUpdateAdminTask()
  const deleteMutation = useDeleteAdminTask()

  const taskTypeOptions =
    catalog?.items.map((item) => ({ label: item.label, value: item.name })) ??
    FALLBACK_TASK_TYPE_OPTIONS
  const descByTaskType = useMemo(() => {
    const map = new Map<string, string>()
    for (const item of catalog?.items ?? []) map.set(item.name, item.description)
    return map
  }, [catalog])

  const openEdit = (task: AdminTask) => {
    setDrawerTask(null)
    setEditing(task)
    form.setFieldsValue({
      taskName: task.taskName,
      taskType: task.taskType,
      source: task.source,
      schedule: task.schedule || undefined,
      isActive: task.isActive,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: TaskFormValues) => {
    if (!editing) return
    const payload = {
      taskName: values.taskName,
      taskType: values.taskType,
      source: values.source,
      schedule: values.schedule,
      isActive: values.isActive,
    }
    try {
      await updateMutation.mutateAsync({ id: editing.id, data: payload })
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

  return (
    <Card variant="borderless">
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
            {viewMode === 'list' ? '按行查看任务配置' : '按日/周/月总览定时分布'}
          </span>
        </div>

        {viewMode === 'list' ? (
          <TaskListView
            tasks={tasks}
            loading={isLoading}
            descByTaskType={descByTaskType}
            onEdit={openEdit}
            onOpenDetail={setDrawerTask}
          />
        ) : (
          <TaskCalendar tasks={tasks} loading={isLoading} onOpenDetail={setDrawerTask} />
        )}
      </div>

      <TaskDetailDrawer
        task={drawerTask}
        description={drawerTask ? descByTaskType.get(drawerTask.taskType) : undefined}
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
            <Select options={taskTypeOptions} />
          </Form.Item>
          <Form.Item name="source" label="来源" rules={[{ required: true }]}>
            <Input placeholder="akshare / tushare / eastmoney" />
          </Form.Item>
          <Form.Item name="schedule" label="执行时间（Cron 表达式）">
            <Input placeholder="例如：0 16 * * 1-5" />
          </Form.Item>
          <Form.Item name="isActive" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
