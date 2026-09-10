import { DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  DatePicker,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Typography,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import {
  useAdminNews,
  useBatchDeleteAdminNews,
  useDeleteAdminNews,
} from '@/hooks/useAdminNews'
import { PAGE_SIZE, type AdminNews } from '@ai-invest/shared'
import { formatDate } from '@/utils/formatters'

interface FilterForm {
  q?: string
  range?: [Dayjs | null, Dayjs | null] | null
}

interface NewsDocPanelProps {
  docType: 'news' | 'announcement'
}

export function NewsDocPanel({ docType }: NewsDocPanelProps) {
  const [filter] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    q: '',
    startDate: undefined as string | undefined,
    endDate: undefined as string | undefined,
    page: 1,
    pageSize: PAGE_SIZE.table,
  })
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const { data, isLoading } = useAdminNews({ docType, ...params })
  const deleteMutation = useDeleteAdminNews()
  const batchDeleteMutation = useBatchDeleteAdminNews()

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
      title: '发布日期',
      dataIndex: 'publishDate',
      key: 'publishDate',
      width: 120,
      render: (v: string | null) => formatDate(v),
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: { showTitle: false },
      render: (value: string, record: AdminNews) =>
        record.sourceUrl ? (
          <Typography.Text ellipsis={{ tooltip: value }}>
            <Typography.Link href={record.sourceUrl} target="_blank" rel="noreferrer">
              {value}
            </Typography.Link>
          </Typography.Text>
        ) : (
          <Typography.Text ellipsis={{ tooltip: value }}>{value}</Typography.Text>
        ),
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: { showTitle: false },
      render: (v: string | null) =>
        v ? (
          <Typography.Text ellipsis={{ tooltip: v }} type="secondary">
            {v}
          </Typography.Text>
        ) : (
          '-'
        ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 120,
      render: (v: string | null) => v || '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      render: (_: unknown, record: AdminNews) => (
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
