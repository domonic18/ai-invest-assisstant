import { FireOutlined } from '@ant-design/icons'
import { Space, TableColumnsType, Tag, Typography } from 'antd'

import type { SectorFundFlow } from '@ai-invest/shared'
import { changeHex } from '@/utils/formatters'

export function formatAmount(value: number | null): string {
  return value === null ? '-' : `${(value / 10000).toFixed(2)} 万`
}

export const columns: TableColumnsType<SectorFundFlow> = [
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
