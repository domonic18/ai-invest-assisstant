import { Button, Space, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'

import type { ApiPaperTradePosition } from '@ai-invest/shared'

import { useStockQuote } from '@/hooks/useStocks'
import { useColorScheme } from '@/stores/settings'
import {
  changeColor,
  fallColor,
  formatNumber,
  formatPercent,
  riseColor,
} from '@/utils/formatters'

import type { OrderPrefill } from './TradingPanel'

/** 标的单元格：名称 + 6 位代码 + 当日涨幅（行情 30s 轮询）；6 位代码可点跳个股详情。 */
export function SymbolCell({ code }: { code: string }) {
  const navigate = useNavigate()
  const isBareCode = /^\d{6}$/.test(code)
  const { data: quote } = useStockQuote(isBareCode ? code : '')
  return (
    <button
      type="button"
      disabled={!isBareCode}
      onClick={() => isBareCode && void navigate(`/stock/${code}`)}
      className={`cursor-pointer text-left leading-tight ${isBareCode ? '' : 'cursor-default'}`}
    >
      <div className="text-white/90">{quote?.name ?? code}</div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-xs text-white/50">{code}</span>
        {quote?.changePct != null && (
          <span
            className="font-mono text-xs"
            style={{ color: changeColor(quote.changePct) }}
          >
            {formatPercent(quote.changePct)}
          </span>
        )}
      </div>
    </button>
  )
}

interface PaperTradePositionsProps {
  positions: ApiPaperTradePosition[]
  loading?: boolean
  /** 账户总资产，仓位% = 市值 / 总资产。 */
  nav?: number | null
  /** 行内「买入/卖出」联动下单卡（回填代码/现价/可卖数量）。 */
  onTrade?: (prefill: OrderPrefill) => void
}

/** 持仓表（无 Card 壳，嵌 tab 使用）：仓位% 按市值/总资产计。 */
export function PaperTradePositions({
  positions,
  loading,
  nav,
  onTrade,
}: PaperTradePositionsProps) {
  const scheme = useColorScheme()

  const columns: ColumnsType<ApiPaperTradePosition> = [
    {
      title: '标的',
      key: 'symbol',
      width: 130,
      render: (_, record) => {
        const code = record.stockCode || record.symbol
        return code ? <SymbolCell code={code} /> : '-'
      },
    },
    {
      title: '方向',
      dataIndex: 'side',
      width: 70,
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
      width: 80,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : String(v)),
    },
    {
      title: '可用',
      dataIndex: 'availableVolume',
      width: 80,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : String(v)),
    },
    {
      title: '仓位',
      key: 'weight',
      width: 80,
      align: 'right',
      render: (_, record) => {
        if (nav == null || nav <= 0 || record.marketValue == null) return '-'
        const pct = (Number(record.marketValue) / nav) * 100
        return `${pct.toFixed(1)}%`
      },
    },
    {
      title: '成本价',
      dataIndex: 'avgPrice',
      width: 95,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 3)),
    },
    {
      title: '现价',
      dataIndex: 'lastPrice',
      width: 95,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 3)),
    },
    {
      title: '市值',
      dataIndex: 'marketValue',
      width: 105,
      align: 'right',
      render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 2)),
    },
    {
      title: '浮盈',
      dataIndex: 'profit',
      width: 105,
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
    {
      title: '盈亏比例',
      dataIndex: 'profitRate',
      width: 95,
      align: 'right',
      render: (v: number | null | undefined) =>
        v == null ? (
          '-'
        ) : (
          <span
            className="font-mono"
            style={{ color: Number(v) >= 0 ? riseColor() : fallColor() }}
          >
            {formatPercent(Number(v))}
          </span>
        ),
    },
    ...(onTrade
      ? [
          {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: unknown, record: ApiPaperTradePosition) => (
              <Space size={4}>
                <Button
                  type="link"
                  size="small"
                  style={{ color: riseColor() }}
                  onClick={() =>
                    onTrade({
                      symbol: record.stockCode || record.symbol,
                      side: 'buy',
                      price: record.lastPrice ?? undefined,
                    })
                  }
                >
                  买入
                </Button>
                <Button
                  type="link"
                  size="small"
                  style={{ color: fallColor() }}
                  disabled={(record.availableVolume ?? 0) <= 0}
                  onClick={() =>
                    onTrade({
                      symbol: record.stockCode || record.symbol,
                      side: 'sell',
                      price: record.lastPrice ?? undefined,
                      volume: record.availableVolume ?? undefined,
                    })
                  }
                >
                  卖出
                </Button>
              </Space>
            ),
          } satisfies ColumnsType<ApiPaperTradePosition>[number],
        ]
      : []),
  ]

  return (
    <div className="space-y-2">
      <Table<ApiPaperTradePosition>
        size="small"
        rowKey={(record) => record.symbol || record.stockCode}
        columns={columns}
        dataSource={positions}
        loading={loading}
        pagination={false}
        locale={{ emptyText: '当前无持仓' }}
        scroll={{ x: 1040 }}
      />
      <Typography.Text type="secondary" className="text-xs">
        仓位 = 市值 ÷ 账户总资产；{scheme === 'cn' ? '红涨绿跌' : '绿涨红跌'}
      </Typography.Text>
    </div>
  )
}
