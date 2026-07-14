import { SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Statistic,
  Table,
  Typography,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import { useFundFlow } from '@/hooks/useFundFlow'
import type { FundFlowData } from '@ai-invest/shared'

interface FilterForm {
  stockCode?: string
  dateRange?: [Dayjs | null, Dayjs | null] | null
}

export function CapitalFlow() {
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    stockCode: '',
    startDate: '',
    endDate: '',
    page: 1,
    pageSize: 20,
  })

  const { data, isLoading } = useFundFlow(params)

  const handleSearch = (values: FilterForm) => {
    const [start, end] = values.dateRange || []
    setParams({
      stockCode: values.stockCode || '',
      startDate: start ? start.format('YYYY-MM-DD') : '',
      endDate: end ? end.format('YYYY-MM-DD') : '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const formatAmount = (value: number | null) => {
    if (value === null || value === undefined) return '-'
    return `${(value / 10000).toFixed(2)} 万`
  }

  const columns = [
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '交易日期', dataIndex: 'date', key: 'date' },
    {
      title: '主力净流入',
      dataIndex: 'mainNetInflow',
      key: 'mainNetInflow',
      render: (value: number | null) => (
        <Typography.Text type={value && value >= 0 ? 'success' : 'danger'}>
          {formatAmount(value)}
        </Typography.Text>
      ),
    },
    {
      title: '超大单',
      dataIndex: 'superLargeNet',
      key: 'superLargeNet',
      render: formatAmount,
    },
    { title: '大单', dataIndex: 'largeNet', key: 'largeNet', render: formatAmount },
    { title: '中单', dataIndex: 'mediumNet', key: 'mediumNet', render: formatAmount },
    { title: '小单', dataIndex: 'smallNet', key: 'smallNet', render: formatAmount },
  ]

  const summary = data?.items || []
  const totalMain = summary.reduce((sum, item) => sum + (item.mainNetInflow || 0), 0)

  return (
    <div className="space-y-6">
      <Typography.Title level={4} className="!mb-0">资金流向</Typography.Title>

      <Form form={form} layout="inline" onFinish={handleSearch} className="mb-4">
        <Form.Item name="stockCode" label="股票代码">
          <Input placeholder="000001" allowClear />
        </Form.Item>
        <Form.Item name="dateRange" label="日期范围">
          <DatePicker.RangePicker />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
            查询
          </Button>
        </Form.Item>
      </Form>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card variant="borderless">
          <Statistic title="记录数" value={data?.total || 0} />
        </Card>
        <Card variant="borderless">
          <Statistic
            title="主力净流入合计"
            value={formatAmount(totalMain)}
            valueStyle={{
              color: totalMain >= 0 ? '#2ea043' : '#f85149',
            }}
          />
        </Card>
        <Card variant="borderless">
          <Statistic title="净流入天数" value={summary.filter((i) => (i.mainNetInflow || 0) >= 0).length} />
        </Card>
      </div>

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey={(record: FundFlowData) => `${record.code}-${record.date}`}
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams((prev) => ({ ...prev, page, pageSize })),
        }}
      />
    </div>
  )
}
