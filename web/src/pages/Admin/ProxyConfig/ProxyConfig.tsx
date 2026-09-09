import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd'
import { useState } from 'react'

import {
  useCreateProxyConfig,
  useDeleteProxyConfig,
  useProxyConfigs,
  useTestProxyConfig,
  useUpdateProxyConfig,
} from '@/hooks/useProxyConfigs'
import type { ProxyConfig, ProxyConfigFormValues } from '@ai-invest/shared'

import { ProxyConfigModal } from './ProxyConfigModal'

export function ProxyConfig() {
  const { data: configs, isLoading, error } = useProxyConfigs()
  const createMutation = useCreateProxyConfig()
  const updateMutation = useUpdateProxyConfig()
  const deleteMutation = useDeleteProxyConfig()
  const testMutation = useTestProxyConfig()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ProxyConfig | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)

  const openCreate = () => {
    setEditing(null)
    setModalOpen(true)
  }

  const openEdit = (config: ProxyConfig) => {
    setEditing(config)
    setModalOpen(true)
  }

  const handleSubmit = async (values: ProxyConfigFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            name: values.name,
            protocol: values.protocol,
            host: values.host,
            port: values.port,
            username: values.username || null,
            password: values.password || undefined,
            isEnabled: values.isEnabled,
          },
        })
        message.success('代理配置已更新')
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          protocol: values.protocol,
          host: values.host,
          port: values.port,
          username: values.username || undefined,
          password: values.password || undefined,
          isEnabled: values.isEnabled,
        })
        message.success('代理配置已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('代理配置已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleToggle = async (config: ProxyConfig, enabled: boolean) => {
    try {
      await updateMutation.mutateAsync({ id: config.id, data: { isEnabled: enabled } })
      message.success(enabled ? `已启用「${config.name}」` : `已禁用「${config.name}」`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleTest = async (config: ProxyConfig) => {
    setTestingId(config.id)
    try {
      const result = await testMutation.mutateAsync(config.id)
      if (result.ok) {
        message.success(`「${config.name}」连通正常（${result.latencyMs}ms）`)
      } else {
        message.error(`「${config.name}」测试失败：${result.error ?? '未知错误'}`)
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '测试失败')
    } finally {
      setTestingId(null)
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '协议',
      dataIndex: 'protocol',
      key: 'protocol',
      width: 90,
      render: (value: string) => <Tag>{value.toUpperCase()}</Tag>,
    },
    {
      title: '地址',
      key: 'endpoint',
      render: (_: unknown, record: ProxyConfig) => (
        <span className="font-mono">
          {record.host}:{record.port}
        </span>
      ),
    },
    { title: '用户名', dataIndex: 'username', key: 'username' },
    {
      title: '密码',
      dataIndex: 'passwordMasked',
      key: 'passwordMasked',
      width: 140,
      ellipsis: true,
    },
    {
      title: '启用',
      dataIndex: 'isEnabled',
      key: 'isEnabled',
      width: 80,
      render: (value: boolean, record: ProxyConfig) => (
        <Switch checked={value} onChange={(checked) => handleToggle(record, checked)} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: ProxyConfig) => (
        <Space>
          <Button
            size="small"
            icon={<ApiOutlined />}
            onClick={() => handleTest(record)}
            loading={testingId === record.id}
          >
            测试
          </Button>
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
      title="代理服务器配置"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增代理
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
        dataSource={configs || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        scroll={{ x: 'max-content' }}
      />

      <ProxyConfigModal
        open={modalOpen}
        editing={editing}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />
    </Card>
  )
}
