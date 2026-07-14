import { DeleteOutlined, EditOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import {
  useAdminNews,
  useCreateAdminNews,
  useDeleteAdminNews,
  useUpdateAdminNews,
} from '@/hooks/useAdminNews'
import type { AdminNews } from '@ai-invest/shared'

interface NewsFormValues {
  stockCode?: string
  docType: string
  title: string
  summary?: string
  content?: string
  source?: string
  sourceUrl?: string
  publishDate?: Dayjs | null
  sentiment?: number | null
  keywords?: string[]
  industryTags?: string[]
}

interface FilterForm {
  stockCode?: string
  docType?: string
  q?: string
}

const DOC_TYPE_OPTIONS = [
  { label: '新闻', value: 'news' },
  { label: '公告', value: 'announcement' },
  { label: '研报', value: 'research' },
]

function SentimentTag({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span>-</span>
  return value >= 0 ? <Tag color="green">{value}</Tag> : <Tag color="red">{value}</Tag>
}

export function AdminNews() {
  const [form] = Form.useForm<NewsFormValues>()
  const [filter] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({ stockCode: '', docType: '', q: '', page: 1, pageSize: 20 })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminNews | null>(null)

  const { data, isLoading } = useAdminNews(params)
  const createMutation = useCreateAdminNews()
  const updateMutation = useUpdateAdminNews()
  const deleteMutation = useDeleteAdminNews()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (item: AdminNews) => {
    setEditing(item)
    form.setFieldsValue({
      stockCode: item.stockCode || undefined,
      docType: item.docType,
      title: item.title,
      summary: item.summary || undefined,
      content: item.content || undefined,
      source: item.source || undefined,
      sourceUrl: item.sourceUrl || undefined,
      publishDate: item.publishDate ? dayjs(item.publishDate) : null,
      sentiment: item.sentiment,
      keywords: item.keywords || [],
      industryTags: item.industryTags || [],
    })
    setModalOpen(true)
  }

  const buildPayload = (values: NewsFormValues) => ({
    stock_code: values.stockCode,
    doc_type: values.docType,
    title: values.title,
    summary: values.summary,
    content: values.content,
    source: values.source,
    source_url: values.sourceUrl,
    publish_date: values.publishDate ? values.publishDate.format('YYYY-MM-DD') : undefined,
    sentiment: values.sentiment ?? undefined,
    keywords: values.keywords,
    industry_tags: values.industryTags,
    extra: {},
  })

  const handleSubmit = async (values: NewsFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: buildPayload(values) })
        message.success('资讯已更新')
      } else {
        await createMutation.mutateAsync(buildPayload(values))
        message.success('资讯已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('资讯已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleSearch = (values: FilterForm) => {
    setParams({
      stockCode: values.stockCode || '',
      docType: values.docType || '',
      q: values.q || '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (value: string, record: AdminNews) => (
        <Space direction="vertical" size={0}>
          <Typography.Text>{value}</Typography.Text>
          {record.sourceUrl && (
            <Typography.Link href={record.sourceUrl} target="_blank" rel="noreferrer">
              原文
            </Typography.Link>
          )}
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'docType', key: 'docType' },
    { title: '股票代码', dataIndex: 'stockCode', key: 'stockCode', render: (v: string | null) => v || '-' },
    { title: '来源', dataIndex: 'source', key: 'source', render: (v: string | null) => v || '-' },
    { title: '发布日期', dataIndex: 'publishDate', key: 'publishDate', render: (v: string | null) => v || '-' },
    { title: '情感', dataIndex: 'sentiment', key: 'sentiment', render: (v: number | null) => <SentimentTag value={v} /> },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      render: (v: string[] | null) =>
        v?.length ? v.map((k) => <Tag key={k}>{k}</Tag>) : '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AdminNews) => (
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
      title="资讯管理"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增资讯
        </Button>
      }
    >
      <Form form={filter} layout="inline" onFinish={handleSearch} className="mb-4">
        <Form.Item name="stockCode" label="股票代码">
          <Input placeholder="000001" allowClear />
        </Form.Item>
        <Form.Item name="docType" label="类型">
          <Select options={DOC_TYPE_OPTIONS} allowClear placeholder="请选择" className="w-32" />
        </Form.Item>
        <Form.Item name="q" label="关键词">
          <Input placeholder="标题/内容" allowClear />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
            查询
          </Button>
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
          onChange: (page, pageSize) => setParams({ ...params, page, pageSize }),
        }}
      />

      <Modal
        title={editing ? '编辑资讯' : '新增资讯'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={720}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="docType" label="类型" rules={[{ required: true }]}>
            <Select options={DOC_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="stockCode" label="股票代码">
            <Input />
          </Form.Item>
          <Form.Item name="source" label="来源">
            <Input />
          </Form.Item>
          <Form.Item name="sourceUrl" label="原文链接">
            <Input />
          </Form.Item>
          <Form.Item name="publishDate" label="发布日期">
            <DatePicker />
          </Form.Item>
          <Form.Item name="sentiment" label="情感值">
            <InputNumber className="w-full" />
          </Form.Item>
          <Form.Item name="keywords" label="关键词">
            <Select mode="tags" placeholder="输入后回车" allowClear />
          </Form.Item>
          <Form.Item name="industryTags" label="行业标签">
            <Select mode="tags" placeholder="输入后回车" allowClear />
          </Form.Item>
          <Form.Item name="summary" label="摘要">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="content" label="正文">
            <Input.TextArea rows={6} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
