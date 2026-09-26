/**
 * 「Agent 记忆」卡片（plan §12.3 管理面）：方法论纪律 + 复盘沉淀的清单、
 * 编辑与停用（archived 不删）。active 条目每日计划生成时全量注入 prompt，
 * 停用即次日不再注入——人工干预记忆的唯一入口（手动沉淀随批次 9 接入）。
 */
import { EditOutlined, StopOutlined, PlayCircleOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { useState } from 'react'

import type { ApiAgentMemory, AgentMemoryType } from '@ai-invest/shared'

import {
  useTradingAgentMemories,
  useUpdateTradingAgentMemory,
  useUpdateTradingAgentMemoryStatus,
} from '@/hooks/useTradingAgent'

const MEM_TYPE_META: Record<AgentMemoryType, { label: string; color: string }> = {
  discipline: { label: '纪律', color: 'red' },
  method: { label: '方法', color: 'geekblue' },
  lesson: { label: '教训', color: 'orange' },
}

const STATUS_FILTERS = [
  { label: '全部', value: 'all' },
  { label: '启用中', value: 'active' },
  { label: '已停用', value: 'archived' },
] as const

function MemoryRow({ memory, onEdit }: { memory: ApiAgentMemory; onEdit: (m: ApiAgentMemory) => void }) {
  const changeStatus = useUpdateTradingAgentMemoryStatus()
  const typeMeta = MEM_TYPE_META[memory.memType] ?? { label: memory.memType, color: 'default' }
  const archived = memory.status === 'archived'

  return (
    <div
      className={`rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 ${
        archived ? 'opacity-55' : ''
      }`}
    >
      <div className="flex items-center gap-2">
        <Tag color={typeMeta.color} className="!mr-0">
          {typeMeta.label}
        </Tag>
        <Typography.Text strong className="min-w-0 flex-1 truncate">
          {memory.title}
        </Typography.Text>
        {memory.source === 'manual' ? (
          <Tag className="!mr-0 !text-[10px]">人工</Tag>
        ) : (
          <Tag className="!mr-0 !text-[10px]">复盘</Tag>
        )}
        {archived && <Tag className="!mr-0 !text-[10px]">已停用</Tag>}
        <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(memory)} aria-label={`编辑 ${memory.title}`} />
        {archived ? (
          <Popconfirm
            title="启用该记忆"
            description="启用后次日计划生成将重新注入此条。"
            okText="启用"
            cancelText="取消"
            onConfirm={() => changeStatus.mutate({ memoryId: memory.id, status: 'active' })}
          >
            <Button type="text" size="small" icon={<PlayCircleOutlined />} aria-label={`启用 ${memory.title}`} />
          </Popconfirm>
        ) : (
          <Popconfirm
            title="停用该记忆"
            description="停用后次日计划生成不再注入此条（不删除，可随时启用）。"
            okText="停用"
            cancelText="取消"
            onConfirm={() => changeStatus.mutate({ memoryId: memory.id, status: 'archived' })}
          >
            <Button type="text" size="small" danger icon={<StopOutlined />} aria-label={`停用 ${memory.title}`} />
          </Popconfirm>
        )}
      </div>
      <Typography.Paragraph type="secondary" className="!mb-0 mt-1 text-xs" ellipsis={{ rows: 2 }}>
        {memory.body}
      </Typography.Paragraph>
    </div>
  )
}

interface EditFormValues {
  memType: AgentMemoryType
  title: string
  body: string
}

function MemoryEditModal({
  memory,
  onClose,
}: {
  memory: ApiAgentMemory | null
  onClose: () => void
}) {
  const [form] = Form.useForm<EditFormValues>()
  const update = useUpdateTradingAgentMemory()

  const submit = async () => {
    if (!memory) return
    const values = await form.validateFields()
    update.mutate(
      { memoryId: memory.id, data: values },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal
      title="编辑记忆"
      open={memory !== null}
      onOk={submit}
      onCancel={onClose}
      okText="保存"
      cancelText="取消"
      confirmLoading={update.isPending}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={
          memory
            ? { memType: memory.memType, title: memory.title, body: memory.body }
            : undefined
        }
      >
        <Form.Item name="memType" label="类型" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'discipline', label: '纪律（硬约束）' },
              { value: 'method', label: '方法（分析框架）' },
              { value: 'lesson', label: '教训' },
            ]}
          />
        </Form.Item>
        <Form.Item name="title" label="标题" rules={[{ required: true, max: 128 }]}>
          <Input />
        </Form.Item>
        <Form.Item name="body" label="正文" rules={[{ required: true }]}>
          <Input.TextArea rows={5} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export function AgentMemoryPanel() {
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'archived'>('all')
  const [editing, setEditing] = useState<ApiAgentMemory | null>(null)
  const { data: memories, isLoading } = useTradingAgentMemories()

  const filtered = (memories ?? []).filter(
    (m) => statusFilter === 'all' || m.status === statusFilter,
  )

  return (
    <Card
      size="small"
      title="Agent 记忆"
      extra={
        <Space size={8}>
          <Typography.Text type="secondary" className="text-xs hidden xl:inline">
            启用中的记忆每日计划生成时注入（含温程《趋势理论》纪律）
          </Typography.Text>
          <Segmented
            size="small"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as 'all' | 'active' | 'archived')}
            options={STATUS_FILTERS.map((f) => ({ label: f.label, value: f.value }))}
          />
        </Space>
      }
    >
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : filtered.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无记忆（复盘沉淀与手动沉淀随批次 9 接入）"
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((memory) => (
            <MemoryRow key={memory.id} memory={memory} onEdit={setEditing} />
          ))}
        </div>
      )}
      <MemoryEditModal memory={editing} onClose={() => setEditing(null)} />
    </Card>
  )
}
