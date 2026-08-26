import {
  CaretRightOutlined,
  DeleteOutlined,
  EditOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  message,
} from 'antd'
import { useState } from 'react'

import {
  useAdminTasks,
  useCreateAdminTask,
  useDeleteAdminTask,
  usePauseAdminTask,
  useResumeAdminTask,
  useTriggerAdminTask,
  useUpdateAdminTask,
} from '@/hooks/useAdminTasks'
import type { AdminTask } from '@ai-invest/shared'
import { formatCronExpression, formatDateTime } from '@/utils/formatters'
import { COLLECTOR_TASK_LABEL, getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'

interface TaskFormValues {
  taskName: string
  taskType: string
  source: string
  schedule?: string
  isActive: boolean
}

const TASK_TYPE_OPTIONS = Object.entries(COLLECTOR_TASK_LABEL).map(([value, label]) => ({
  label,
  value,
}))

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  pending: 'orange',
  idle: 'default',
}

export function AdminTasks() {
  const [form] = Form.useForm<TaskFormValues>()
  const [params, setParams] = useState({ page: 1, pageSize: 20 })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminTask | null>(null)

  const { data, isLoading } = useAdminTasks(params)
  const createMutation = useCreateAdminTask()
  const updateMutation = useUpdateAdminTask()
  const deleteMutation = useDeleteAdminTask()
  const pauseMutation = usePauseAdminTask()
  const resumeMutation = useResumeAdminTask()
  const triggerMutation = useTriggerAdminTask()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (task: AdminTask) => {
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
    const payload = {
      task_name: values.taskName,
      task_type: values.taskType,
      source: values.source,
      schedule: values.schedule,
      is_active: values.isActive,
    }
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: payload })
        message.success('任务已更新')
      } else {
        await createMutation.mutateAsync(payload)
        message.success('任务已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('任务已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleTrigger = async (id: number) => {
    try {
      await triggerMutation.mutateAsync(id)
      message.success('任务已触发')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '触发失败')
    }
  }

  const handlePause = async (id: number) => {
    try {
      await pauseMutation.mutateAsync(id)
      message.success('任务已暂停')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '暂停失败')
    }
  }

  const handleResume = async (id: number) => {
    try {
      await resumeMutation.mutateAsync(id)
      message.success('任务已恢复')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败')
    }
  }

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'taskName',
      key: 'taskName',
      render: (_: string, record: AdminTask) =>
        `${getSourceLabel(record.source)} - ${getTaskLabel(record.taskType)}`,
    },
    { title: '任务类型', dataIndex: 'taskType', key: 'taskType', render: (value: string) => getTaskLabel(value) },
    { title: '来源', dataIndex: 'source', key: 'source', render: (value: string | null) => getSourceLabel(value) },
    {
      title: '执行时间',
      dataIndex: 'schedule',
      key: 'schedule',
      render: (v: string | null) =>
        v ? (
          <Tooltip title={`Cron: ${v}`}>
            <span>{formatCronExpression(v)}</span>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      key: 'isActive',
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '最近运行',
      dataIndex: 'lastStatus',
      key: 'lastStatus',
      render: (value: string, record: AdminTask) => (
        <Space>
          <Tag color={STATUS_COLORS[value] || 'default'}>{value}</Tag>
          <span className="text-gray-400">{formatDateTime(record.lastRunAt)}</span>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AdminTask) => (
        <Space>
          <Button
            size="small"
            icon={<CaretRightOutlined />}
            loading={triggerMutation.isPending}
            onClick={() => handleTrigger(record.id)}
          >
            触发
          </Button>
          {record.isActive ? (
            <Button
              size="small"
              icon={<PauseCircleOutlined />}
              loading={pauseMutation.isPending}
              onClick={() => handlePause(record.id)}
            >
              暂停
            </Button>
          ) : (
            <Button
              size="small"
              icon={<PlayCircleOutlined />}
              loading={resumeMutation.isPending}
              onClick={() => handleResume(record.id)}
            >
              恢复
            </Button>
          )}
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="采集任务管理"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增任务
        </Button>
      }
    >
      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams({ page, pageSize }),
        }}
      />

      <Modal
        title={editing ? '编辑任务' : '新增任务'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="taskName" label="任务名称" rules={[{ required: true }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="taskType" label="任务类型" rules={[{ required: true }]}>
            <Select options={TASK_TYPE_OPTIONS} />
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
