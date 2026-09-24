import { DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  DatePicker,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import {
  useAdminTelegraph,
  useBatchDeleteAdminTelegraph,
  useDeleteAdminTelegraph,
} from '@/hooks/useAdminTelegraph'
import { PAGE_SIZE, type AdminTelegraph } from '@ai-invest/shared'
import { formatDateTime } from '@/utils/formatters'

interface FilterForm {
  q?: string
  range?: [Dayjs | null, Dayjs | null] | null
}

function importanceColor(value: number): string {
  if (value >= 2) return 'red'
  if (value === 1) return 'orange'
  return 'default'
}

export function TelegraphPanel() {
  const [filter] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    q: '',
    startDate: undefined as string | undefined,
    endDate: undefined as string | undefined,
    page: 1,
    pageSize: PAGE_SIZE.table,
  })
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const { data, isLoading } = useAdminTelegraph(params)
  const deleteMutation = useDeleteAdminTelegraph()
  const batchDeleteMutation = useBatchDeleteAdminTelegraph()

  const handleSearch = (values: FilterForm) => {
    const [start, end] = values.range ?? [null, null]
    setParams({
      q: values.q || '',
      startDate: start?.format('YYYY-MM-DD'),
      endDate: end?.format('YYYY-MM-DD'),
      page: 1,
      pageSize: params.pageSize,
    })
    setSelectedIds([])
  }

  const handleReset = () => {
    filter.resetFields()
    setParams({
      q: '',
      startDate: undefined,
      endDate: undefined,
      page: 1,
      pageSize: params.pageSize,
    })
    setSelectedIds([])
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleBatchDelete = async () => {
    try {
      const deleted = await batchDeleteMutation.mutateAsync(selectedIds)
      message.success(`已删除 ${deleted} 条`)
      setSelectedIds([])
    } catch (err) {
      message.error(err instanceof Error ? err.message : '批量删除失败')
    }
  }

  const columns = [
    {
      title: '发布时间',
      dataIndex: 'publishTime',
      key: 'publishTime',
      width: 160,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '内容',
      dataIndex: 'title',
      key: 'title',
      ellipsis: { showTitle: false },
      render: (value: string | null, record: AdminTelegraph) => {
        const text = value || record.content || ''
        return (
          <Typography.Text ellipsis={{ tooltip: text }}>{text || '-'}</Typography.Text>
        )
      },
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (v: string | null) => v || '-',
    },
    {
      title: '重要性',
      dataIndex: 'importance',
      key: 'importance',
      width: 90,
      render: (v: number | null) =>
        v === null || v === undefined ? (
          '-'
        ) : (
          <Tag color={importanceColor(v)}>{v}</Tag>
        ),
    },
    {
      title: 'AI 分级',
      dataIndex: 'aiScore',
      key: 'aiScore',
      width: 90,
      render: (v: number | null) =>
        v === null || v === undefined ? '-' : <Tag color="blue">{v}</Tag>,
    },
    {
      title: '关联标的',
      dataIndex: 'stockCodes',
      key: 'stockCodes',
      width: 160,
      ellipsis: { showTitle: false },
      render: (v: string[] | null) =>
        v?.length ? (
          <Typography.Text ellipsis={{ tooltip: v.join('、') }}>
            {v.join('、')}
          </Typography.Text>
        ) : (
          '-'
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      render: (_: unknown, record: AdminTelegraph) => (
        <Popconfirm title="确认删除该条？" onConfirm={() => handleDelete(record.id)}>
          <Button size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <>
      <Form form={filter} layout="inline" onFinish={handleSearch} className="mb-4">
        <Form.Item name="q" label="关键词">
          <Input placeholder="标题/内容" allowClear />
        </Form.Item>
        <Form.Item name="range" label="发布日期">
          <DatePicker.RangePicker allowClear />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
              查询
            </Button>
            <Button onClick={handleReset}>重置</Button>
          </Space>
        </Form.Item>
      </Form>

      <div className="mb-3">
        <Popconfirm
          title={`确认删除选中的 ${selectedIds.length} 条？`}
          onConfirm={handleBatchDelete}
          disabled={selectedIds.length === 0}
        >
          <Button
            danger
            icon={<DeleteOutlined />}
            disabled={selectedIds.length === 0}
            loading={batchDeleteMutation.isPending}
          >
            批量删除{selectedIds.length > 0 ? `（${selectedIds.length}）` : ''}
          </Button>
        </Popconfirm>
      </div>

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        rowSelection={{
          selectedRowKeys: selectedIds,
          onChange: (keys) => setSelectedIds(keys as number[]),
        }}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => {
            setParams({ ...params, page, pageSize })
            setSelectedIds([])
          },
        }}
      />
    </>
  )
}
