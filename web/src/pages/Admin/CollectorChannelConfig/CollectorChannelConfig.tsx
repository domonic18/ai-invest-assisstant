import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useState } from 'react'

import {
  useCollectorChannelConfigs,
  useCreateCollectorChannelConfig,
  useDeleteCollectorChannelConfig,
  useUpdateCollectorChannelConfig,
} from '@/hooks/useCollectorChannelConfigs'
import type {
  CollectorChannelConfig,
  CollectorChannelConfigFormValues,
  CollectorTaskName,
} from '@ai-invest/shared'

import { CollectorChannelConfigModal } from './CollectorChannelConfigModal'

const SOURCE_LABEL: Record<string, string> = {
  sina: '新浪财经',
  eastmoney: '东方财富',
  ths: '同花顺',
  cninfo: '巨潮资讯',
}

const DATA_TYPE_LABEL: Record<CollectorTaskName, string> = {
  kline: 'K 线',
  auction: '集合竞价',
  'fund-flow': '资金流向',
  news: '新闻',
  'company-profile': '公司概况',
  disclosure: '公告披露',
  'sector-fund-flow': '板块资金流向',
  'dragon-list': '龙虎榜',
  'research-report': '个股研报',
  macro: '宏观经济',
}

export function CollectorChannelConfig() {
  const { data: configs, isLoading, error } = useCollectorChannelConfigs()
  const createMutation = useCreateCollectorChannelConfig()
  const updateMutation = useUpdateCollectorChannelConfig()
  const deleteMutation = useDeleteCollectorChannelConfig()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<CollectorChannelConfig | null>(null)

  const openCreate = () => {
    setEditing(null)
    setModalOpen(true)
  }

  const openEdit = (config: CollectorChannelConfig) => {
    setEditing(config)
    setModalOpen(true)
  }

  const handleSubmit = async (values: CollectorChannelConfigFormValues) => {
    try {
      const payload = {
        name: values.name,
        base_url: values.baseUrl || undefined,
        api_key: values.apiKey || undefined,
        is_enabled: values.isEnabled,
        supported_data_types: values.supportedDataTypes,
      }
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: payload,
        })
        message.success('渠道配置已更新')
      } else {
        await createMutation.mutateAsync({
          source: values.source,
          ...payload,
        })
        message.success('渠道配置已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('渠道配置已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleToggle = async (config: CollectorChannelConfig, checked: boolean) => {
    try {
      await updateMutation.mutateAsync({
        id: config.id,
        data: { is_enabled: checked },
      })
      message.success(`${config.name} 已${checked ? '启用' : '禁用'}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '状态更新失败')
    }
  }

  const columns = [
    { title: '渠道', dataIndex: 'name', key: 'name' },
    {
      title: '标识',
      dataIndex: 'source',
      key: 'source',
      render: (value: string) => SOURCE_LABEL[value] || value,
    },
    {
      title: 'API 地址',
      dataIndex: 'baseUrl',
      key: 'baseUrl',
      render: (value: string | null) => value || '-',
    },
    {
      title: 'API Key',
      dataIndex: 'apiKeyMasked',
      key: 'apiKeyMasked',
      render: (value: string | null) => value || '-',
    },
    {
      title: '支持的数据类型',
      dataIndex: 'supportedDataTypes',
      key: 'supportedDataTypes',
      render: (value: string[]) => (
        <Space size="small" wrap>
          {value.map((type) => (
            <Tag key={type}>{DATA_TYPE_LABEL[type as CollectorTaskName] || type}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '启用',
      dataIndex: 'isEnabled',
      key: 'isEnabled',
      render: (value: boolean, record: CollectorChannelConfig) => (
        <Switch
          checked={value}
          onChange={(checked) => handleToggle(record, checked)}
          loading={updateMutation.isPending}
        />
      ),
    },
    {
      title: '状态',
      dataIndex: 'isEnabled',
      key: 'status',
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: CollectorChannelConfig) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
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
      title="采集渠道配置"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增渠道
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

      <Alert
        message="说明"
        description={
          <Typography.Text type="secondary">
            配置每个渠道支持的数据类型。任务触发时，系统只会从支持该任务且已启用的渠道中自动选择；你也可以在任务弹窗中手动指定渠道。
          </Typography.Text>
        }
        type="info"
        showIcon
        className="mb-4"
      />

      <Table
        dataSource={configs || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
      />

      <CollectorChannelConfigModal
        open={modalOpen}
        editing={editing}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />
    </Card>
  )
}
