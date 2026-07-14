import {
  EditOutlined,
  EyeOutlined,
  FileTextOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import {
  useResearch,
  useResearchReport,
  useSummarizeResearchReport,
} from '@/hooks/useResearch'
import type { ResearchReport } from '@ai-invest/shared'

interface FilterForm {
  stockCode?: string
  q?: string
  dateRange?: [Dayjs | null, Dayjs | null] | null
}

export function Research() {
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    stockCode: '',
    q: '',
    startDate: '',
    endDate: '',
    page: 1,
    pageSize: 20,
  })
  const [detailId, setDetailId] = useState<number | null>(null)
  const [summaryId, setSummaryId] = useState<number | null>(null)

  const { data, isLoading } = useResearch(params)
  const { data: detail } = useResearchReport(detailId)
  const summarizeMutation = useSummarizeResearchReport()

  const handleSearch = (values: FilterForm) => {
    const [start, end] = values.dateRange || []
    setParams({
      stockCode: values.stockCode || '',
      q: values.q || '',
      startDate: start ? start.format('YYYY-MM-DD') : '',
      endDate: end ? end.format('YYYY-MM-DD') : '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const handleSummarize = async (id: number) => {
    setSummaryId(id)
    try {
      const summary = await summarizeMutation.mutateAsync(id)
      message.success(`摘要：${summary}`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成摘要失败')
    } finally {
      setSummaryId(null)
    }
  }

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (value: string, record: ResearchReport) => (
        <Space>
          <FileTextOutlined />
          <span>{value}</span>
          {record.stockCode && <Tag>{record.stockCode}</Tag>}
        </Space>
      ),
    },
    { title: '来源', dataIndex: 'source', key: 'source', render: (value: string | null) => value || '-' },
    { title: '发布日期', dataIndex: 'publishDate', key: 'publishDate', render: (value: string | null) => value || '-' },
    {
      title: '情感',
      dataIndex: 'sentiment',
      key: 'sentiment',
      render: (value: number | null) =>
        value === null ? '-' : value > 0 ? <Tag color="green">{value}</Tag> : <Tag color="red">{value}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: ResearchReport) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => setDetailId(record.id)}
          >
            详情
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            loading={summaryId === record.id}
            onClick={() => handleSummarize(record.id)}
          >
            摘要
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card title="研报中心" variant="borderless">
      <Form
        form={form}
        layout="inline"
        onFinish={handleSearch}
        className="mb-4"
      >
        <Form.Item name="stockCode" label="股票代码">
          <Input placeholder="000001" allowClear />
        </Form.Item>
        <Form.Item name="q" label="关键词">
          <Input placeholder="标题/内容" allowClear />
        </Form.Item>
        <Form.Item name="dateRange" label="发布日期">
          <DatePicker.RangePicker />
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
          onChange: (page, pageSize) => setParams((prev) => ({ ...prev, page, pageSize })),
        }}
      />

      <Modal
        title={detail?.title || '研报详情'}
        open={!!detailId}
        onCancel={() => setDetailId(null)}
        footer={null}
        width={800}
      >
        {detail && (
          <Space direction="vertical" className="w-full">
            <Typography.Text type="secondary">
              {detail.source} · {detail.publishDate}
            </Typography.Text>
            {detail.summary && (
              <Typography.Paragraph>
                <strong>摘要：</strong>
                {detail.summary}
              </Typography.Paragraph>
            )}
            <Typography.Paragraph>
              {detail.content || '暂无正文'}
            </Typography.Paragraph>
          </Space>
        )}
      </Modal>
    </Card>
  )
}
