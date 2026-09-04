import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useMemo, useState } from 'react'

import { useCollectorChannelConfigs } from '@/hooks/useCollectorChannelConfigs'
import {
  useCollectorDataTypeChannels,
  useReplaceDataTypeChannels,
} from '@/hooks/useCollectorDataTypeChannels'
import type { CollectorDataTypeChannel, CollectorTaskName } from '@ai-invest/shared'

import { DATA_TYPE_LABEL } from './constants'

export function DataTypePriorityPanel() {
  const { data: dataTypes, isLoading, error } = useCollectorDataTypeChannels()
  const { data: allChannels } = useCollectorChannelConfigs()
  const replaceMutation = useReplaceDataTypeChannels()

  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [draft, setDraft] = useState<CollectorDataTypeChannel[]>([])
  const [dirty, setDirty] = useState(false)
  const [channelToAdd, setChannelToAdd] = useState<number | null>(null)

  const current = useMemo(
    () => dataTypes?.find((item) => item.dataType === selectedType) ?? null,
    [dataTypes, selectedType],
  )

  useEffect(() => {
    if (!selectedType && dataTypes?.length) {
      setSelectedType(dataTypes[0].dataType)
    }
  }, [dataTypes, selectedType])

  useEffect(() => {
    setDraft(current?.channels ?? [])
    setDirty(false)
    setChannelToAdd(null)
  }, [current])

  const move = (index: number, offset: number) => {
    const target = index + offset
    if (target < 0 || target >= draft.length) return
    const next = [...draft]
    ;[next[index], next[target]] = [next[target], next[index]]
    setDraft(next)
    setDirty(true)
  }

  const remove = (channelId: number) => {
    setDraft(draft.filter((item) => item.channelId !== channelId))
    setDirty(true)
  }

  const add = () => {
    if (channelToAdd == null || !allChannels) return
    const channel = allChannels.find((item) => item.id === channelToAdd)
    if (!channel) return
    setDraft([
      ...draft,
      {
        channelId: channel.id,
        source: channel.source,
        name: channel.name,
        isEnabled: channel.isEnabled,
        priority: draft.length + 1,
      },
    ])
    setChannelToAdd(null)
    setDirty(true)
  }

  const save = async () => {
    if (!selectedType) return
    try {
      await replaceMutation.mutateAsync({
        dataType: selectedType,
        items: draft.map((item, index) => ({
          channel_id: item.channelId,
          priority: index + 1,
        })),
      })
      message.success('渠道优先级已保存')
      setDirty(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  const addableChannels = (allChannels ?? []).filter(
    (channel) => !draft.some((item) => item.channelId === channel.id),
  )

  const columns = [
    {
      title: '顺序',
      key: 'order',
      width: 70,
      render: (_: unknown, __: CollectorDataTypeChannel, index: number) => index + 1,
    },
    { title: '渠道', dataIndex: 'name', key: 'name' },
    {
      title: '标识',
      dataIndex: 'source',
      key: 'source',
    },
    {
      title: '状态',
      dataIndex: 'isEnabled',
      key: 'isEnabled',
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: CollectorDataTypeChannel, index: number) => (
        <Space>
          <Button
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={index === 0}
            onClick={() => move(index, -1)}
          />
          <Button
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={index === draft.length - 1}
            onClick={() => move(index, 1)}
          />
          <Popconfirm title="确认移除？" onConfirm={() => remove(record.channelId)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
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
            配置每个数据类型可用的采集渠道及优先级。任务执行时按顺序尝试：排第一的渠道失败后自动切换到下一个渠道。
          </Typography.Text>
        }
        type="info"
        showIcon
        className="mb-4"
      />

      <Space className="mb-4" wrap>
        <Select
          style={{ minWidth: 220 }}
          value={selectedType}
          onChange={setSelectedType}
          loading={isLoading}
          options={(dataTypes ?? []).map((item) => ({
            value: item.dataType,
            label: DATA_TYPE_LABEL[item.dataType as CollectorTaskName] || item.dataType,
          }))}
        />
        <Select
          style={{ minWidth: 200 }}
          placeholder="选择要添加的渠道"
          value={channelToAdd}
          onChange={setChannelToAdd}
          options={addableChannels.map((channel) => ({
            value: channel.id,
            label: channel.name,
          }))}
        />
        <Button
          icon={<PlusOutlined />}
          onClick={add}
          disabled={channelToAdd == null}
        >
          添加
        </Button>
        <Button
          type="primary"
          onClick={save}
          disabled={!dirty}
          loading={replaceMutation.isPending}
        >
          保存
        </Button>
      </Space>

      <Table
        dataSource={draft}
        columns={columns}
        rowKey="channelId"
        loading={isLoading}
        pagination={false}
        locale={{ emptyText: '该数据类型暂未配置渠道' }}
      />
    </div>
  )
}
