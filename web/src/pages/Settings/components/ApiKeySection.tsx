/**
 * MCP 访问密钥 section：自助签发 / 列表 / 吊销。
 * 明文 token 仅在签发响应中出现一次，服务端只存哈希。
 */

import { CopyOutlined, PlusOutlined } from '@ant-design/icons'
import { apiKeyScopeLabel } from '@ai-invest/shared'
import type { ApiKey, ApiKeyCreateRequest, ApiKeyIssued } from '@ai-invest/shared'
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import {
  useCreateMyApiKey,
  useMyApiKeys,
  usePurgeMyApiKey,
  useRevokeMyApiKey,
} from '@/hooks/useApiKeys'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { HintBox } from './SettingHints'

const EXPIRY_OPTIONS = [
  { value: 0, label: '永久有效' },
  { value: 30, label: '30 天' },
  { value: 90, label: '90 天' },
  { value: 365, label: '1 年' },
]

interface CreateFormValues {
  name: string
  expiresInDays: number
}

function keyStatus(key: ApiKey): { label: string; color: string } {
  if (key.revokedAt) return { label: '已吊销', color: 'red' }
  if (key.expiresAt && new Date(key.expiresAt) <= new Date()) {
    return { label: '已过期', color: 'orange' }
  }
  return { label: '有效', color: 'green' }
}

export function ApiKeySection() {
  const { message } = App.useApp()
  const keysQ = useMyApiKeys()
  const createMutation = useCreateMyApiKey()
  const revokeMutation = useRevokeMyApiKey()
  const purgeMutation = usePurgeMyApiKey()
  const [form] = Form.useForm<CreateFormValues>()
  const [createOpen, setCreateOpen] = useState(false)
  const [issued, setIssued] = useState<ApiKeyIssued | null>(null)

  const mcpEndpoint = `${window.location.origin}/api/v1/mcp`

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      message.success('已复制')
    } catch {
      message.error('复制失败，请手动选择文本')
    }
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    const days = values.expiresInDays
    const payload: ApiKeyCreateRequest = {
      name: values.name.trim(),
      expiresAt:
        days > 0 ? new Date(Date.now() + days * 86_400_000).toISOString() : null,
    }
    const created = await createMutation.mutateAsync(payload)
    setCreateOpen(false)
    form.resetFields()
    setIssued(created)
  }

  const columns: ColumnsType<ApiKey> = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (name: string) => <span className="text-[13px]">{name}</span>,
    },
    {
      title: 'Key 前缀',
      dataIndex: 'keyPrefix',
      render: (prefix: string) => (
        <span className="font-mono text-xs text-[#8a8f98]">{prefix}…</span>
      ),
    },
    {
      title: '权限',
      dataIndex: 'scopes',
      render: (scopes: string[]) => (
        <Space size={4} wrap>
          {scopes.map((scope) => (
            <Tag key={scope} bordered={false}>
              {apiKeyScopeLabel(scope)}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      render: (value: string) => (
        <span className="text-xs text-[#8a8f98]">{formatDateTime(value)}</span>
      ),
    },
    {
      title: '最近使用',
      dataIndex: 'lastUsedAt',
      render: (value: string | null) => (
        <span className="text-xs text-[#8a8f98]">{formatDateTime(value)}</span>
      ),
    },
    {
      title: '有效期',
      dataIndex: 'expiresAt',
      render: (value: string | null) => (
        <span className="text-xs text-[#8a8f98]">
          {value ? formatDate(value) : '永久'}
        </span>
      ),
    },
    {
      title: '状态',
      key: 'status',
      render: (_, key) => {
        const status = keyStatus(key)
        return (
          <Tag bordered={false} color={status.color}>
            {status.label}
          </Tag>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      render: (_, key) =>
        key.revokedAt ? (
          <Popconfirm
            title="删除该密钥记录？"
            description="记录删除后不可恢复。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => purgeMutation.mutate(key.id)}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        ) : (
          <Popconfirm
            title="吊销该密钥？"
            description="使用该 Key 的客户端将立即失去访问权限。"
            okText="吊销"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => revokeMutation.mutate(key.id)}
          >
            <Button type="link" size="small" danger>
              吊销
            </Button>
          </Popconfirm>
        ),
    },
  ]

  return (
    <>
      <Card
        variant="borderless"
        title="MCP 访问密钥"
        extra={
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            签发新 Key
          </Button>
        }
      >
        <div className="flex items-center gap-2 flex-wrap mb-3">
          <span className="text-xs text-[#8a8f98]">MCP 端点</span>
          <span className="font-mono text-xs text-[#f0f1f5]">{mcpEndpoint}</span>
          <Button
            type="text"
            size="small"
            icon={<CopyOutlined />}
            onClick={() => handleCopy(mcpEndpoint)}
          />
        </div>

        <Table<ApiKey>
          rowKey="id"
          size="small"
          columns={columns}
          dataSource={keysQ.data ?? []}
          loading={keysQ.isLoading}
          pagination={false}
          locale={{ emptyText: '尚未签发密钥' }}
        />

        <HintBox>
          密钥用于外部 Agent（Claude Code / 飞书助手等）以 MCP 协议只读访问平台投研数据。
          请求时携带 <code>Authorization: Bearer &lt;token&gt;</code>；明文只在签发时展示一次，
          遗忘后请吊销并重新签发。密钥跟随账号状态，账号停用后立即失效。
        </HintBox>
      </Card>

      <Modal
        title="签发 MCP 访问密钥"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        okText="签发"
        cancelText="取消"
        confirmLoading={createMutation.isPending}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ expiresInDays: 0 }}
          className="pt-2"
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入名称' },
              { max: 100, message: '名称不超过 100 字' },
            ]}
          >
            <Input placeholder="如：飞书投资助手" autoFocus />
          </Form.Item>
          <Form.Item name="expiresInDays" label="有效期">
            <Select options={EXPIRY_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="密钥已签发"
        open={issued != null}
        onCancel={() => setIssued(null)}
        footer={[
          <Button key="close" type="primary" onClick={() => setIssued(null)}>
            我已保存
          </Button>,
        ]}
      >
        <Typography.Paragraph type="secondary" className="!text-xs">
          {issued?.note}
        </Typography.Paragraph>
        <Input.TextArea
          value={issued?.token ?? ''}
          readOnly
          autoSize={{ minRows: 2, maxRows: 3 }}
          className="font-mono"
        />
        <Button
          icon={<CopyOutlined />}
          className="mt-2"
          onClick={() => issued && handleCopy(issued.token)}
        >
          复制 Token
        </Button>
      </Modal>
    </>
  )
}
