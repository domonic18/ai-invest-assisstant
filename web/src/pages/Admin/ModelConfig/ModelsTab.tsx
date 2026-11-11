import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Popconfirm,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import {
  useCreateLLMConfig,
  useDeleteLLMConfig,
  useLLMConfigs,
  useTestLLMConfig,
  useUpdateLLMConfig,
} from '@/hooks/useModelConfig'
import { LLM_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { LLMConfig, LLMConfigCapabilities, LLMConfigFormValues } from '@ai-invest/shared'

import { ModelFormModal } from './ModelFormModal'

const PROTOCOL_META: Record<string, { label: string; color: string }> = {
  openai: { label: 'OpenAI 兼容', color: 'geekblue' },
  anthropic: { label: 'Anthropic', color: 'purple' },
  systemone: { label: 'System One', color: 'cyan' },
}

const PURPOSE_LABEL: Record<string, string> = {
  chat: '对话/分析',
  embedding: '向量嵌入',
  vision: '视觉识别',
  decision: '结构化判断',
}

function getCapabilities(config: LLMConfig | null): LLMConfigCapabilities {
  return (config?.extra?.capabilities ?? {}) as LLMConfigCapabilities
}

function DegradedTag({ degradedUntil }: { degradedUntil: string | null }) {
  if (!degradedUntil) return null
  const minutes = dayjs(degradedUntil).diff(dayjs(), 'minute')
  if (minutes <= 0) return null
  return (
    <Tooltip title="额度耗尽或连接中断进入冷却，引用该条目的槽位自动切备用；冷却结束后自动恢复">
      <Tag color="orange">冷却中 · 约 {minutes} 分钟后恢复</Tag>
    </Tooltip>
  )
}

export function ModelsTab() {
  const { data: configs, isLoading, error } = useLLMConfigs()
  const createMutation = useCreateLLMConfig()
  const updateMutation = useUpdateLLMConfig()
  const deleteMutation = useDeleteLLMConfig()
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
      // 载荷收敛：vision 能力仅 chat/vision 携带，防隐藏开关的历史脏值入库
      const capabilitiesVision =
        values.purpose === 'chat' || values.purpose === 'vision'
          ? values.vision === true
          : false
      if (editing) {
        // extra 整体覆盖写，须保留已有键仅更新 capabilities.vision
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            name: values.name,
            provider: values.provider,
            protocol: values.protocol,
            baseUrl: values.baseUrl,
            modelName: values.modelName,
            apiKey: values.apiKey || undefined,
            isActive: values.isActive,
            purpose: values.purpose,
            extra: {
              ...editing.extra,
              capabilities: { ...getCapabilities(editing), vision: capabilitiesVision },
            },
          },
        })
        message.success('配置已更新')
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          provider: values.provider,
          protocol: values.protocol,
          baseUrl: values.baseUrl,
          modelName: values.modelName,
          apiKey: values.apiKey,
          isActive: values.isActive,
          purpose: values.purpose,
          extra: { capabilities: { vision: capabilitiesVision } },
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
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (value: string, record: LLMConfig) => (
        <Space>
          <span>{value}</span>
          <DegradedTag degradedUntil={record.degradedUntil} />
        </Space>
      ),
    },
    {
      title: '供应商',
      dataIndex: 'provider',
      key: 'provider',
      render: (value: string) =>
        LLM_PROVIDER_PRESETS[value]?.label ?? (value === 'custom' ? '自定义' : value),
    },
    {
      title: '协议',
      dataIndex: 'protocol',
      key: 'protocol',
      width: 110,
      render: (value: string) => {
        const meta = PROTOCOL_META[value]
        return <Tag color={meta?.color ?? 'default'}>{meta?.label ?? value}</Tag>
      },
    },
    { title: '模型', dataIndex: 'modelName', key: 'modelName' },
    {
      title: '用途',
      dataIndex: 'purpose',
      key: 'purpose',
      width: 110,
      render: (value: LLMConfig['purpose']) => PURPOSE_LABEL[value] ?? value,
    },
    {
      title: 'API Key',
      dataIndex: 'apiKeyMasked',
      key: 'apiKeyMasked',
      width: 160,
      ellipsis: true,
    },
    {
      title: '能力',
      key: 'capabilities',
      render: (_: unknown, record: LLMConfig) =>
        getCapabilities(record).vision ? <Tag color="geekblue">视觉</Tag> : null,
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
      title="模型条目"
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

      <ModelFormModal
        open={modalOpen}
        editing={editing}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        onTest={() => editing && handleTest(editing)}
        testing={testMutation.isPending}
        loading={createMutation.isPending || updateMutation.isPending}
      />
    </Card>
  )
}
