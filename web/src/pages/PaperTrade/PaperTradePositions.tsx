import { Card, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ApiPaperTradePosition } from '@ai-invest/shared'

import { useColorScheme } from '@/stores/settings'
import { fallColor, formatNumber, riseColor } from '@/utils/formatters'

interface PaperTradePositionsProps {
  positions: ApiPaperTradePosition[]
  loading?: boolean
}

export function PaperTradePositions({ positions, loading }: PaperTradePositionsProps) {
  const scheme = useColorScheme()

  const columns: ColumnsType<ApiPaperTradePosition> = [
    {
      title: '标的',
      dataIndex: 'stockCode',
      width: 110,
      render: (_, record) => record.stockCode || record.symbol || '-',
    },
    {
      title: '方向',
      dataIndex: 'side',
      width: 80,
      render: (side: number | null | undefined) =>
        side === 1 ? (
          <span style={{ color: riseColor() }}>买入</span>
        ) : side === 2 ? (
          <span style={{ color: fallColor() }}>卖出</span>
        ) : (
          '-'
        ),
    },
    {
      title: '持仓',
      dataIndex: 'volume',
      width: 90,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : String(v)),
    },
    {
      title: '可用',
      dataIndex: 'availableVolume',
      width: 90,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : String(v)),
    },
    {
      title: '成本价',
      dataIndex: 'avgPrice',
      width: 100,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 3)),
    },
    {
      title: '现价',
      dataIndex: 'lastPrice',
      width: 100,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 3)),
    },
    {
      title: '市值',
      dataIndex: 'marketValue',
      width: 110,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 2)),
    },
    {
      title: '浮盈',
      dataIndex: 'profit',
      align: 'right',
      render: (v: number | null | undefined) =>
        v == null ? (
          '-'
        ) : (
          <span style={{ color: v >= 0 ? riseColor() : fallColor() }}>
            {v >= 0 ? '+' : ''}
            {formatNumber(Number(v), 2)}
          </span>
        ),
    },
  ]

  return (
    <Card
      size="small"
      title="持仓"
      extra={
        <Typography.Text type="secondary" className="text-xs">
          {scheme === 'cn' ? '红涨绿跌' : '绿涨红跌'}
        </Typography.Text>
      }
    >
      <Table<ApiPaperTradePosition>
        size="small"
        rowKey={(record) => record.symbol || record.stockCode}
        columns={columns}
        dataSource={positions}
        loading={loading}
        pagination={false}
        locale={{ emptyText: '当前无持仓' }}
        scroll={{ x: 720 }}
      />
    </Card>
  )
}
