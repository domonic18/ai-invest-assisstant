import { Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { AuctionDayStat } from '../utils'
import { featureLabel } from '../utils'

interface AuctionStatsTableProps {
  seriesNames: string[]
  stats: AuctionDayStat[]
}

const FEATURE_TAG: Record<string, { color: string }> = {
  high: { color: 'red' },
  low: { color: 'green' },
}

/** 各交易日竞价统计表（原型双表中数据可支撑的一张）：成交额 / 量比 / 特征。 */
export function AuctionStatsTable({ seriesNames, stats }: AuctionStatsTableProps) {
  const columns: ColumnsType<AuctionDayStat> = [
    {
      title: '日期',
      dataIndex: 'date',
      width: 110,
      render: (value: string) => value.slice(5),
    },
    ...seriesNames.map((name, i) => ({
      title: name,
      key: `series-${i}`,
      align: 'right' as const,
      render: (_: unknown, row: AuctionDayStat) =>
        row.values[i] === null ? '-' : (row.values[i] as number).toFixed(2),
    })),
    {
      title: '合计',
      dataIndex: 'total',
      align: 'right' as const,
      width: 90,
      render: (value: number | null) => (value === null ? '-' : value.toFixed(2)),
    },
    {
      title: '量比',
      dataIndex: 'ratio',
      align: 'right' as const,
      width: 80,
      render: (value: number | null) => (value === null ? '-' : `${value.toFixed(2)}×`),
    },
    {
      title: '特征',
      dataIndex: 'feature',
      width: 80,
      render: (value: AuctionDayStat['feature']) =>
        value === null ? (
          '-'
        ) : (
          <Tag color={FEATURE_TAG[value]?.color ?? 'default'}>{featureLabel(value)}</Tag>
        ),
    },
  ]

  const ordered = [...stats].reverse()
  return (
    <Table<AuctionDayStat>
      rowKey="date"
      columns={columns}
      dataSource={ordered}
      size="small"
      pagination={{ pageSize: 10, showSizeChanger: false, hideOnSinglePage: true }}
    />
  )
}
