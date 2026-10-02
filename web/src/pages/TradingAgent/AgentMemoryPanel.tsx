/**
 * 「经验总结」卡片（tab 唯一管理面，批次 9 后合并原只读浏览视图）：
 * 记忆库清单（复盘自动沉淀 + 手动沉淀）、手动沉淀、编辑、删除（物理删除）
 * 与停用/启用（archived 可逆，次日计划不再注入）。active 条目每日计划
 * 生成时全量注入 prompt；自动沉淀同标题去重 + 刷时间。
 */
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  StopOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
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

import { useAgentKey } from './agentKeyContext'
import { formatDateTime } from '@/utils/formatters'
import {
  useCreateTradingAgentMemory,
  useDeleteTradingAgentMemory,
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
  const agentKey = useAgentKey()
  const changeStatus = useUpdateTradingAgentMemoryStatus(agentKey)
  const remove = useDeleteTradingAgentMemory(agentKey)
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
        <span className="hidden text-xs text-white/40 xl:inline">{formatDateTime(memory.updatedAt)}</span>
        <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(memory)} aria-label={`编辑 ${memory.title}`} />
        {archived ? (
          <Popconfirm
            title="启用该经验"
            description="启用后次日计划生成将重新注入此条。"
            okText="启用"
            cancelText="取消"
            onConfirm={() => changeStatus.mutate({ memoryId: memory.id, status: 'active' })}
          >
            <Button type="text" size="small" icon={<PlayCircleOutlined />} aria-label={`启用 ${memory.title}`} />
          </Popconfirm>
        ) : (
          <Popconfirm
            title="停用该经验"
            description="停用后次日计划生成不再注入此条（可随时重新启用）。"
            okText="停用"
            cancelText="取消"
            onConfirm={() => changeStatus.mutate({ memoryId: memory.id, status: 'archived' })}
          >
            <Button type="text" size="small" danger icon={<StopOutlined />} aria-label={`停用 ${memory.title}`} />
          </Popconfirm>
        )}
        <Popconfirm
          title="删除该经验"
          description={
            memory.source === 'auto'
              ? '物理删除且不可恢复；下次复盘若再产出同标题经验会重新沉淀。'
              : '物理删除且不可恢复。'
          }
          okText="删除"
          okButtonProps={{ danger: true }}
          cancelText="取消"
          onConfirm={() => remove.mutate(memory.id)}
        >
          <Button type="text" size="small" danger icon={<DeleteOutlined />} aria-label={`删除 ${memory.title}`} />
        </Popconfirm>
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

/** target: null=关闭，'new'=新建（手动沉淀），行对象=编辑。 */
function MemoryFormModal({
  target,
  onClose,
}: {
  target: ApiAgentMemory | 'new' | null
  onClose: () => void
}) {
  const [form] = Form.useForm<EditFormValues>()
  const agentKey = useAgentKey()
  const create = useCreateTradingAgentMemory(agentKey)
  const update = useUpdateTradingAgentMemory(agentKey)
  const isCreate = target === 'new'

  const submit = async () => {
    const values = await form.validateFields()
    if (isCreate) {
      create.mutate(values, { onSuccess: onClose })
    } else if (target) {
      update.mutate({ memoryId: target.id, data: values }, { onSuccess: onClose })
    }
  }

  return (
    <Modal
      title={isCreate ? '沉淀经验' : '编辑经验'}
      open={target !== null}
      onOk={submit}
      onCancel={onClose}
      okText={isCreate ? '沉淀' : '保存'}
      cancelText="取消"
      confirmLoading={create.isPending || update.isPending}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={
          isCreate
            ? { memType: 'lesson' as AgentMemoryType }
            : target
              ? { memType: target.memType, title: target.title, body: target.body }
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
  const [formTarget, setFormTarget] = useState<ApiAgentMemory | 'new' | null>(null)
  const agentKey = useAgentKey()
  const { data: memories, isLoading } = useTradingAgentMemories(agentKey)

  const filtered = (memories ?? []).filter(
    (m) => statusFilter === 'all' || m.status === statusFilter,
  )

  return (
    <Card
      size="small"
      title="经验总结"
      extra={
        <Space size={8}>
          <Typography.Text type="secondary" className="text-xs hidden xl:inline">
            启用中的经验每日计划生成时注入 Agent
          </Typography.Text>
          <Segmented
            size="small"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as 'all' | 'active' | 'archived')}
            options={STATUS_FILTERS.map((f) => ({ label: f.label, value: f.value }))}
          />
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setFormTarget('new')}
          >
            沉淀经验
          </Button>
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
          description="暂无经验总结（复盘自动沉淀 + 「沉淀经验」手动添加）"
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((memory) => (
            <MemoryRow key={memory.id} memory={memory} onEdit={setFormTarget} />
          ))}
        </div>
      )}
      <MemoryFormModal target={formTarget} onClose={() => setFormTarget(null)} />
    </Card>
  )
}
