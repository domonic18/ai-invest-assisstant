import { DeleteOutlined, FilePdfOutlined, SearchOutlined } from '@ant-design/icons'
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

import { fetchResearchPdfUrl } from '@/api/research'
import { useAdminNews, useDeleteAdminNews } from '@/hooks/useAdminNews'
import { PAGE_SIZE, type AdminNews } from '@ai-invest/shared'
import { formatDate } from '@/utils/formatters'

interface FilterForm {
  q?: string
  broker?: string
  range?: [Dayjs | null, Dayjs | null] | null
}

function extraText(record: AdminNews, key: string): string | null {
  const value = record.extra?.[key]
  return typeof value === 'string' && value ? value : null
}

export function ResearchPanel() {
  const [filter] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    q: '',
    broker: '',
    startDate: undefined as string | undefined,
    endDate: undefined as string | undefined,
    page: 1,
    pageSize: PAGE_SIZE.table,
  })
  const [previewingId, setPreviewingId] = useState<number | null>(null)

  const { data, isLoading } = useAdminNews({ docType: 'research', ...params })
  const deleteMutation = useDeleteAdminNews()

  const handleSearch = (values: FilterForm) => {
    const [start, end] = values.range ?? [null, null]
    setParams({
      q: values.q || '',
      broker: values.broker || '',
      startDate: start?.format('YYYY-MM-DD'),
      endDate: end?.format('YYYY-MM-DD'),
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const handleReset = () => {
    filter.resetFields()
    setParams({
      q: '',
      broker: '',
      startDate: undefined,
      endDate: undefined,
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const handlePreview = async (record: AdminNews) => {
    setPreviewingId(record.id)
    try {
      const url = await fetchResearchPdfUrl(record.id)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'PDF 获取失败')
    } finally {
      setPreviewingId(null)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('研报已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: { showTitle: false },
      render: (value: string) => (
        <Typography.Text ellipsis={{ tooltip: value }}>{value}</Typography.Text>
      ),
    },
    {
      title: '券商',
      key: 'broker',
      width: 140,
      render: (_: unknown, record: AdminNews) => extraText(record, 'broker') || '-',
    },
    {
      title: '股票',
      dataIndex: 'stockCode',
      key: 'stockCode',
      width: 110,
      render: (v: string | null) => v || '-',
    },
    {
      title: '行业',
      key: 'industry',
      width: 120,
      render: (_: unknown, record: AdminNews) => extraText(record, 'industry') || '-',
    },
    {
      title: '发布日期',
      dataIndex: 'publishDate',
      key: 'publishDate',
      width: 120,
      render: (v: string | null) => formatDate(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: AdminNews) => (
        <Space>
          <Button
            size="small"
            icon={<FilePdfOutlined />}
            loading={previewingId === record.id}
            onClick={() => handlePreview(record)}
          >
            预览
          </Button>
          <Popconfirm title="确认删除该研报？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <Form form={filter} layout="inline" onFinish={handleSearch} className="mb-4">
        <Form.Item name="q" label="关键词">
          <Input placeholder="标题/内容" allowClear />
        </Form.Item>
        <Form.Item name="broker" label="券商">
          <Input placeholder="券商名称" allowClear />
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

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => setParams({ ...params, page, pageSize }),
        }}
      />
    </>
  )
}
