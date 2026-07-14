import { SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import { useAuctionData } from '@/hooks/useAuction'
import type { AuctionData } from '@ai-invest/shared'

interface FilterForm {
  stockCode: string
  tradeDate?: Dayjs | null
}

function PriceList({ prices, volumes, type }: { prices: number[]; volumes: number[]; type: 'bid' | 'ask' }) {
  return (
    <div className="space-y-1">
      {prices.slice(0, 5).map((price, idx) => (
        <div key={idx} className="flex justify-between gap-4">
          <Tag color={type === 'bid' ? 'green' : 'red'}>{price.toFixed(2)}</Tag>
          <span className="text-gray-400">{volumes[idx] ?? '-'}</span>
        </div>
      ))}
    </div>
  )
}

export function AuctionReview() {
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    stockCode: '',
    tradeDate: dayjs().format('YYYY-MM-DD'),
    page: 1,
    pageSize: 20,
  })

  const { data, isLoading, error } = useAuctionData(params.stockCode, {
    tradeDate: params.tradeDate,
    page: params.page,
    pageSize: params.pageSize,
  })

  const handleSearch = (values: FilterForm) => {
    setParams({
      stockCode: values.stockCode,
      tradeDate: values.tradeDate ? values.tradeDate.format('YYYY-MM-DD') : dayjs().format('YYYY-MM-DD'),
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const columns = [
    { title: '时间', dataIndex: 'time', key: 'time' },
    {
      title: '成交价',
      dataIndex: 'price',
      key: 'price',
      render: (value: number) => value.toFixed(3),
    },
    { title: '成交量', dataIndex: 'volume', key: 'volume' },
    {
      title: '买档（价/量）',
      key: 'bids',
      render: (_: unknown, record: AuctionData) => (
        <PriceList prices={record.bidPrices} volumes={record.bidVolumes} type="bid" />
      ),
    },
    {
      title: '卖档（价/量）',
      key: 'asks',
      render: (_: unknown, record: AuctionData) => (
        <PriceList prices={record.askPrices} volumes={record.askVolumes} type="ask" />
      ),
    },
  ]

  const items = data?.items || []
  const lastPrice = items[items.length - 1]?.price

  return (
    <div className="space-y-6">
      <Typography.Title level={4} className="!mb-0">集合竞价复盘</Typography.Title>

      <Form form={form} layout="inline" onFinish={handleSearch} className="mb-4">
        <Form.Item name="stockCode" label="股票代码" rules={[{ required: true }]}>
          <Input placeholder="000001" allowClear />
        </Form.Item>
        <Form.Item name="tradeDate" label="交易日期">
          <DatePicker />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
            查询
          </Button>
        </Form.Item>
      </Form>

      {!params.stockCode && !isLoading && (
        <Typography.Text type="secondary">请输入股票代码查询集合竞价数据。</Typography.Text>
      )}

      {error && (
        <Typography.Text type="danger">
          {error instanceof Error ? error.message : '加载失败'}
        </Typography.Text>
      )}

      {params.stockCode && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card variant="borderless">
              <Statistic title="记录数" value={data?.total || 0} />
            </Card>
            <Card variant="borderless">
              <Statistic
                title="最新成交价"
                value={lastPrice ?? '-'}
                precision={3}
              />
            </Card>
            <Card variant="borderless">
              <Statistic title="最新时间" value={items[items.length - 1]?.time ?? '-'} />
            </Card>
          </div>

          <Table
            dataSource={items}
            columns={columns}
            rowKey={(record: AuctionData) => `${record.date}-${record.time}`}
            loading={isLoading}
            pagination={{
              current: data?.page,
              pageSize: data?.pageSize,
              total: data?.total,
              onChange: (page, pageSize) => setParams((prev) => ({ ...prev, page, pageSize })),
            }}
          />
        </>
      )}
    </div>
  )
}
