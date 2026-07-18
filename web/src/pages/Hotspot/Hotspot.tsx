import { FireOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import { useHotspot } from '@/hooks/useHotspot'
import type { SectorFundFlow } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { changeHex } from '@/utils/formatters'

interface FilterForm {
  sectorType?: string
  tradeDate?: Dayjs | null
}

export function Hotspot() {
  useColorScheme()
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    sectorType: '',
    tradeDate: '',
    page: 1,
    pageSize: 20,
  })

  const { data, isLoading } = useHotspot(params)

  const handleSearch = (values: FilterForm) => {
    setParams({
      sectorType: values.sectorType || '',
      tradeDate: values.tradeDate ? values.tradeDate.format('YYYY-MM-DD') : '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const formatAmount = (value: number | null) =>
    value === null ? '-' : `${(value / 10000).toFixed(2)} 万`

  const columns = [
    {
      title: '板块',
      dataIndex: 'sectorName',
      key: 'sectorName',
      render: (value: string, record: SectorFundFlow) => (
        <Space>
          <FireOutlined />
          <span>{value}</span>
          <Tag>{record.sectorType}</Tag>
        </Space>
      ),
    },
    { title: '交易日期', dataIndex: 'tradeDate', key: 'tradeDate' },
    {
      title: '主力净流入',
      dataIndex: 'mainNetInflow',
      key: 'mainNetInflow',
      render: (value: number | null) => (
        <Typography.Text style={{ color: changeHex(value) }}>
          {formatAmount(value)}
        </Typography.Text>
      ),
    },
    { title: '超大单', dataIndex: 'superLargeNet', key: 'superLargeNet', render: formatAmount },
    { title: '大单', dataIndex: 'largeNet', key: 'largeNet', render: formatAmount },
    { title: '中单', dataIndex: 'mediumNet', key: 'mediumNet', render: formatAmount },
    { title: '小单', dataIndex: 'smallNet', key: 'smallNet', render: formatAmount },
    {
      title: '领涨股',
      key: 'topStock',
      render: (_: unknown, record: SectorFundFlow) =>
        record.topStockCode ? `${record.topStockName} (${record.topStockCode})` : '-',
    },
  ]

  return (
    <Card title="热点追踪" variant="borderless">
      <Form form={form} layout="inline" onFinish={handleSearch} className="mb-4">
        <Form.Item name="sectorType" label="板块类型">
          <Input placeholder="industry / concept" allowClear />
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

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey={(record: SectorFundFlow) => `${record.sectorCode}-${record.sectorType}-${record.tradeDate}`}
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams((prev) => ({ ...prev, page, pageSize })),
        }}
      />
    </Card>
  )
}
