import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  PlusOutlined,
  StarOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useState } from 'react'

import {
  useCreateLLMConfig,
  useDeleteLLMConfig,
  useLLMConfigs,
  useSetDefaultLLMConfig,
  useTestLLMConfig,
  useUpdateLLMConfig,
} from '@/hooks/useLLMConfigs'
import type { LLMConfig, LLMConfigFormValues } from '@ai-invest/shared'

import { LLMConfigModal } from './LLMConfigModal'

const PROVIDER_LABEL: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  deepseek: 'DeepSeek',
  zhipu: '智谱 GLM',
  custom: '自定义',
}

export function LLMConfig() {
  const { data: configs, isLoading, error } = useLLMConfigs()
  const createMutation = useCreateLLMConfig()
  const updateMutation = useUpdateLLMConfig()
  const deleteMutation = useDeleteLLMConfig()
  const setDefaultMutation = useSetDefaultLLMConfig()
  const testMutation = useTestLLMConfig()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<LLMConfig | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)

  const openCreate = () => {
    setEditing(null)
    setModalOpen(true)
  }

  const openEdit = (config: LLMConfig) => {
    setEditing(config)
    setModalOpen(true)
  }

  const handleSubmit = async (values: LLMConfigFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            name: values.name,
            provider: values.provider,
            base_url: values.baseUrl,
            model_name: values.modelName,
            api_key: values.apiKey || undefined,
            is_default: values.isDefault,
            is_active: values.isActive,
          },
        })
        message.success('配置已更新')
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          provider: values.provider,
          base_url: values.baseUrl,
          model_name: values.modelName,
          api_key: values.apiKey,
          is_default: values.isDefault,
          is_active: values.isActive,
        })
        message.success('配置已创建')
      }
      setModalOpen(false)
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

  const handleSetDefault = async (config: LLMConfig) => {
    try {
      await setDefaultMutation.mutateAsync(config.id)
      message.success(`已将「${config.name}」设为默认模型`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '设置失败')
    }
  }

  const handleTest = async (config: LLMConfig) => {
    setTestingId(config.id)
    try {
      const result = await testMutation.mutateAsync(config.id)
      if (result.status === 'success') {
        message.success(`${config.name} 连通正常`)
      } else {
        message.error(`${config.name} 测试失败：${result.detail}`)
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
      title: '供应商',
      dataIndex: 'provider',
      key: 'provider',
      render: (value: string) => PROVIDER_LABEL[value] || value,
    },
    { title: '模型', dataIndex: 'modelName', key: 'modelName' },
    {
      title: 'API Key',
      dataIndex: 'apiKeyMasked',
      key: 'apiKeyMasked',
      width: 160,
      ellipsis: true,
    },
    {
      title: '默认',
      dataIndex: 'isDefault',
      key: 'isDefault',
      render: (value: boolean) =>
        value ? <Tag color="gold">默认</Tag> : null,
    },
    {
      title: '启用',
      dataIndex: 'isActive',
      key: 'isActive',
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '最后测试',
      key: 'lastTest',
      width: 220,
      ellipsis: true,
      render: (_: unknown, record: LLMConfig) => {
        if (!record.lastTestStatus) return '-'
        return record.lastTestStatus === 'success' ? (
          <Space>
            <CheckCircleOutlined className="text-green-500" />
            <Typography.Text type="secondary">{record.lastTestedAt}</Typography.Text>
          </Space>
        ) : (
          <Space>
            <CloseCircleOutlined className="text-red-500" />
            <Typography.Text type="secondary">{record.lastTestError}</Typography.Text>
          </Space>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: LLMConfig) => (
        <Space>
          <Button
            size="small"
            icon={<ExperimentOutlined />}
            onClick={() => handleTest(record)}
            loading={testingId === record.id}
          >
            测试
          </Button>
          {!record.isDefault && (
            <Button
              size="small"
              icon={<StarOutlined />}
              onClick={() => handleSetDefault(record)}
              loading={setDefaultMutation.isPending}
            >
              设默认
            </Button>
          )}
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除？"
            onConfirm={() => handleDelete(record.id)}
          >
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
      title="LLM 配置"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增模型
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

      <LLMConfigModal
        open={modalOpen}
        editing={editing}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />
    </Card>
  )
}
