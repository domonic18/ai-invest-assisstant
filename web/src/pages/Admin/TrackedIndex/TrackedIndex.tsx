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
  message,
} from 'antd'
import { useState } from 'react'

import {
  useDeleteTrackedIndex,
  useToggleTrackedIndex,
  useTrackedIndexes,
  useUpdateTrackedIndex,
  useCreateTrackedIndex,
} from '@/hooks/useTrackedIndexes'
import { changeColor, formatPercent } from '@/utils/formatters'
import type { TrackedIndexConfig, TrackedIndexFormValues } from '@ai-invest/shared'

import { TrackedIndexModal } from './TrackedIndexModal'

const SOURCE_LABEL: Record<string, string> = {
  sina: '新浪财经',
  eastmoney: '东方财富',
  tushare: 'Tushare Pro',
}

export function TrackedIndex() {
  const { data: indexes, isLoading, error } = useTrackedIndexes()
  const createMutation = useCreateTrackedIndex()
  const updateMutation = useUpdateTrackedIndex()
  const deleteMutation = useDeleteTrackedIndex()
  const toggleMutation = useToggleTrackedIndex()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<TrackedIndexConfig | null>(null)

  const openCreate = () => {
    setEditing(null)
    setModalOpen(true)
  }

  const openEdit = (config: TrackedIndexConfig) => {
    setEditing(config)
    setModalOpen(true)
  }

  const handleSubmit = async (values: TrackedIndexFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            index_name: values.indexName,
            market_category: values.marketCategory,
            data_source: values.dataSource,
            sort_order: values.sortOrder,
            is_enabled: values.isEnabled,
          },
        })
        message.success('配置已更新')
      } else {
        await createMutation.mutateAsync({
          index_code: values.indexCode,
          index_name: values.indexName,
          market_category: values.marketCategory,
          data_source: values.dataSource,
          sort_order: values.sortOrder,
          is_enabled: values.isEnabled,
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

  const handleToggle = async (config: TrackedIndexConfig) => {
    try {
      await toggleMutation.mutateAsync(config.id)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const columns = [
    {
      title: '指数代码',
      dataIndex: 'indexCode',
      key: 'indexCode',
      width: 110,
    },
    { title: '名称', dataIndex: 'indexName', key: 'indexName' },
    {
      title: '市场类别',
      dataIndex: 'marketCategory',
      key: 'marketCategory',
      width: 100,
      render: (value: string) =>
        value === '全球' ? <Tag color="geekblue">全球</Tag> : <Tag color="red">A 股</Tag>,
    },
    {
      title: '数据源',
      dataIndex: 'dataSource',
      key: 'dataSource',
      width: 110,
      render: (value: string) => SOURCE_LABEL[value] || value,
    },
    {
      title: '最新值',
      key: 'latest',
      width: 180,
      render: (_: unknown, record: TrackedIndexConfig) => {
        if (record.latestClose === null || record.latestClose === undefined) return '-'
        return (
          <Space size={8}>
            <span className="tabular-nums">{record.latestClose}</span>
            {record.latestChangePct !== null && record.latestChangePct !== undefined && (
              <span className={`tabular-nums ${changeColor(record.latestChangePct)}`}>
                {formatPercent(record.latestChangePct)}
              </span>
            )}
          </Space>
        )
      },
    },
    { title: '排序', dataIndex: 'sortOrder', key: 'sortOrder', width: 80 },
    {
      title: '启用',
      dataIndex: 'isEnabled',
      key: 'isEnabled',
      width: 90,
      render: (value: boolean, record: TrackedIndexConfig) => (
        <Switch
          checked={value}
          loading={toggleMutation.isPending && toggleMutation.variables === record.id}
          onChange={() => handleToggle(record)}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: TrackedIndexConfig) => (
        <Space>
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
      title="跟踪指数"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增指数
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
        dataSource={indexes || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        scroll={{ x: 'max-content' }}
      />

      <TrackedIndexModal
        open={modalOpen}
        editing={editing}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />
    </Card>
  )
}
