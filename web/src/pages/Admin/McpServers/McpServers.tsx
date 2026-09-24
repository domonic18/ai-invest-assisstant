import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  List,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ApiMcpServerConfig, ApiMcpServerTestResult } from '@ai-invest/shared'
import { useState } from 'react'

import {
  useCreateMcpServer,
  useDeleteMcpServer,
  useMcpServers,
  useTestMcpServer,
  useTestMcpServerDraft,
  useUpdateMcpServer,
} from '@/hooks/useMcpServers'
import { formatDateTime } from '@/utils/formatters'

import { McpServerModal } from './McpServerModal'
import type { McpServerPayload } from './mcpServerForm'

const TRANSPORT_LABEL: Record<string, string> = {
  http: 'HTTP',
  sse: 'SSE',
  stdio: 'stdio',
}

function renderTarget(record: ApiMcpServerConfig) {
  if (record.transportType === 'stdio') {
    return [record.command, ...(record.args ?? [])].filter(Boolean).join(' ') || '-'
  }
  return record.url || '-'
}

export function McpServers() {
  const { data: servers, isLoading, error } = useMcpServers()
  const createMutation = useCreateMcpServer()
  const updateMutation = useUpdateMcpServer()
  const deleteMutation = useDeleteMcpServer()
  const testMutation = useTestMcpServer()
  const testDraftMutation = useTestMcpServerDraft()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ApiMcpServerConfig | null>(null)
  const [testingId, setTestingId] = useState<number | 'draft' | null>(null)
  const [testResult, setTestResult] = useState<
    (ApiMcpServerTestResult & { name: string }) | null
  >(null)

  const showResult = (name: string, result: ApiMcpServerTestResult) => {
    setTestResult({ ...result, name })
    if (result.ok) {
      message.success(`${name} 连接正常，发现 ${result.toolCount} 个工具`)
    } else {
      message.error(`${name} 连接失败`)
    }
  }

  const handleTest = async (record: ApiMcpServerConfig) => {
    setTestingId(record.id)
    try {
      showResult(record.name, await testMutation.mutateAsync(record.id))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '测试失败')
    } finally {
      setTestingId(null)
    }
  }

  const handleTestDraft = async (payload: McpServerPayload) => {
    setTestingId('draft')
    try {
      showResult(editing?.name ?? payload.name, await testDraftMutation.mutateAsync(payload))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '测试失败')
    } finally {
      setTestingId(null)
    }
  }

  const handleSubmit = async (payload: McpServerPayload) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: payload })
        message.success('配置已更新')
      } else {
        await createMutation.mutateAsync(payload)
        message.success('配置已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleToggle = async (record: ApiMcpServerConfig, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({ id: record.id, data: { enabled } })
      message.success(enabled ? `已启用「${record.name}」` : `已停用「${record.name}」`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('配置已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '通道',
      dataIndex: 'transportType',
      key: 'transportType',
      width: 90,
      render: (value: string) => <Tag color="geekblue">{TRANSPORT_LABEL[value] || value}</Tag>,
    },
    {
      title: '目标',
      key: 'target',
      ellipsis: true,
      render: (_: unknown, record: ApiMcpServerConfig) => (
        <Typography.Text code>{renderTarget(record)}</Typography.Text>
      ),
    },
    {
      title: '超时',
      dataIndex: 'timeoutSeconds',
      key: 'timeoutSeconds',
      width: 80,
      render: (value: number) => `${value}s`,
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 90,
      render: (value: boolean, record: ApiMcpServerConfig) => (
        <Switch
          checked={value}
          loading={updateMutation.isPending && updateMutation.variables?.id === record.id}
          onChange={(checked) => handleToggle(record, checked)}
        />
      ),
    },
    {
      title: '最近测试',
      key: 'lastStatus',
      width: 110,
      render: (_: unknown, record: ApiMcpServerConfig) =>
        record.lastStatus === 'ok' ? (
          <Tag color="green">正常</Tag>
        ) : record.lastStatus === 'failed' ? (
          <Tag color="red">失败</Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 170,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_: unknown, record: ApiMcpServerConfig) => (
        <Space>
          <Button
            size="small"
            icon={<ExperimentOutlined />}
            loading={testingId === record.id}
            onClick={() => handleTest(record)}
          >
            测试
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditing(record)
              setModalOpen(true)
            }}
          >
            编辑
          </Button>
          <Popconfirm title="确认删除该 MCP 服务配置？" onConfirm={() => handleDelete(record.id)}>
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
      title="MCP 服务"
      variant="borderless"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditing(null)
            setModalOpen(true)
          }}
        >
          新增服务
        </Button>
      }
    >
      {error && (
        <Alert
          message="加载失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
          className="mb-4"
        />
      )}

      <Table
        dataSource={servers || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        scroll={{ x: 'max-content' }}
      />

      <McpServerModal
        open={modalOpen}
        editing={editing}
        loading={createMutation.isPending || updateMutation.isPending}
        testing={testingId === 'draft'}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        onTestDraft={handleTestDraft}
      />

      <Modal
        title={`工具清单：${testResult?.name ?? ''}`}
        open={testResult !== null}
        onCancel={() => setTestResult(null)}
        footer={
          <Button type="primary" onClick={() => setTestResult(null)}>
            关闭
          </Button>
        }
      >
        {testResult?.ok ? (
          <>
            <Typography.Paragraph type="secondary">
              共 {testResult.toolCount} 个工具
            </Typography.Paragraph>
            <List
              size="small"
              dataSource={testResult.tools}
              renderItem={(tool) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<ApiOutlined />}
                    title={<Typography.Text code>{tool.name}</Typography.Text>}
                    description={tool.description ?? '-'}
                  />
                </List.Item>
              )}
            />
          </>
        ) : (
          <Alert
            type="error"
            showIcon
            message="连接失败"
            description={testResult?.error ?? '未知错误'}
          />
        )}
      </Modal>
    </Card>
  )
}
