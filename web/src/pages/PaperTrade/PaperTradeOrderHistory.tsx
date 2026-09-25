import { SyncOutlined } from '@ant-design/icons'
import { Button, DatePicker, Popconfirm, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import type {
  ApiPaperTradeExecution,
  ApiPaperTradeOrder,
} from '@ai-invest/shared'

import {
  useCancelPaperTradeOrder,
  useDelayedPaperTradeSync,
  usePaperTradeExecutions,
  usePaperTradeOrders,
} from '@/hooks/usePaperTrade'
import {
  fallColor,
  formatDateTime,
  formatNumber,
  riseColor,
} from '@/utils/formatters'
import {
  paperTradeOrderStatus,
  paperTradeOrderType,
} from '@ai-invest/shared'

import { isMarketOpen } from './tradingRules'

const PAGE_SIZE = 20

/** 可撤单状态：已报 / 部分成交。 */
const CANCELLABLE_STATUSES = new Set([1, 2])

function sideCell(side: number | null | undefined) {
  if (side === 1) return <span style={{ color: riseColor() }}>买入</span>
  if (side === 2) return <span style={{ color: fallColor() }}>卖出</span>
  return '-'
}

function sourceCell(source?: string | null) {
  if (source === 'agent') return <Tag color="gold">Agent</Tag>
  if (source === 'manual') return <Tag>人工</Tag>
  return '-'
}

/** 6 位代码优先；回报 wire 无 stockCode 时从掘金 symbol 取点号后段。 */
function stockCell(record: { stockCode?: string | null; symbol: string }) {
  if (record.stockCode) return record.stockCode
  const symbol = record.symbol || ''
  return symbol.includes('.') ? symbol.split('.')[1] : symbol
}

const baseOrderColumns: ColumnsType<ApiPaperTradeOrder> = [
  {
    title: '时间',
    dataIndex: 'counterCreatedAt',
    width: 170,
    render: (v: string | null | undefined) => formatDateTime(v ?? null),
  },
  {
    title: '标的',
    key: 'stock',
    width: 90,
    render: (_, record) => stockCell(record),
  },
  {
    title: '方向',
    dataIndex: 'side',
    width: 80,
    render: (side: number) => sideCell(side),
  },
  {
    title: '类型',
    dataIndex: 'orderType',
    width: 80,
    render: (v: number) => paperTradeOrderType(v),
  },
  {
    title: '价格',
    dataIndex: 'price',
    width: 100,
    align: 'right',
    render: (v: number) => formatNumber(Number(v), 3),
  },
  {
    title: '数量',
    dataIndex: 'volume',
    width: 90,
    align: 'right',
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 80,
    render: (v: number) => paperTradeOrderStatus(v),
  },
  {
    title: '来源',
    dataIndex: 'orderSource',
    width: 80,
    render: (v: string | undefined) => sourceCell(v),
  },
  {
    title: '拒单原因',
    dataIndex: 'ordRejReasonDetail',
    render: (detail: string | null | undefined, record) =>
      record.ordRejReason == null ? (
        '-'
      ) : (
        <Typography.Text style={{ color: fallColor() }}>
          {detail || `原因码 ${record.ordRejReason}`}
        </Typography.Text>
      ),
  },
]

const executionColumns: ColumnsType<ApiPaperTradeExecution> = [
  {
    title: '时间',
    dataIndex: 'counterCreatedAt',
    width: 170,
    render: (v: string | null | undefined) => formatDateTime(v ?? null),
  },
  {
    title: '标的',
    key: 'stock',
    width: 90,
    render: (_, record) => stockCell(record),
  },
  {
    title: '方向',
    dataIndex: 'side',
    width: 80,
    render: (side: number | null | undefined) => sideCell(side),
  },
  {
    title: '价格',
    dataIndex: 'price',
    width: 100,
    align: 'right',
    render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 3)),
  },
  {
    title: '数量',
    dataIndex: 'volume',
    width: 90,
    align: 'right',
    render: (v: number | null | undefined) => (v == null ? '-' : String(v)),
  },
  {
    title: '成交额',
    dataIndex: 'turnover',
    width: 110,
    align: 'right',
    render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 2)),
  },
  {
    title: '手续费',
    dataIndex: 'commission',
    align: 'right',
    render: (v: number | null | undefined) => (v == null ? '-' : formatNumber(Number(v), 2)),
  },
]

interface HistoryState {
  tradeDate: Dayjs | null
  page: number
}

/** 同步柜台按钮（配 usePaperTradeSyncAction 的 pending 使用）。 */
export function SyncButton({
  pending,
  onClick,
}: {
  pending: boolean
  onClick: () => void
}) {
  return (
    <Button size="small" icon={<SyncOutlined />} loading={pending} onClick={onClick}>
      同步柜台
    </Button>
  )
}

/** 委托列表（默认最近交易日 + 可撤单；交易时段 30s 自动推进状态）。 */
export function PaperTradeOrdersPanel({
  accountId,
  onSynced,
}: {
  accountId: number
  onSynced?: () => Promise<unknown>
}) {
  const [{ tradeDate, page }, setState] = useState<HistoryState>({
    tradeDate: null,
    page: 1,
  })
  const query = usePaperTradeOrders(
    accountId,
    tradeDate ? tradeDate.format('YYYY-MM-DD') : undefined,
    page,
    PAGE_SIZE,
    // 交易时段 30s 轮询推进委托状态；refetch 间隙重估，收盘自动停
    () => (isMarketOpen() ? 30_000 : false),
  )
  const cancelMutation = useCancelPaperTradeOrder()
  const scheduleSync = useDelayedPaperTradeSync()

  // 撤单后即时同步柜台，再在 t+3s/t+15s 静默补同步（撤成回报异步到达）
  const handleCancel = async (clOrdId: string) => {
    try {
      await cancelMutation.mutateAsync({ accountId, clOrdId })
      scheduleSync(accountId)
      await onSynced?.()
    } catch {
      // 柜台拒撤/403 已由 mutation onError 弹窗
    }
  }

  const orderColumns: ColumnsType<ApiPaperTradeOrder> = [
    ...baseOrderColumns,
    {
      title: '操作',
      key: 'action',
      width: 70,
      render: (_, record) =>
        CANCELLABLE_STATUSES.has(record.status) ? (
          <Popconfirm
            title="确认撤销该笔委托？"
            okText="撤单"
            cancelText="取消"
            onConfirm={() => void handleCancel(record.clOrdId)}
          >
            <Button type="link" size="small" danger disabled={cancelMutation.isPending}>
              撤单
            </Button>
          </Popconfirm>
        ) : null,
    },
  ]

  return (
    <div className="space-y-3">
      <DatePicker
        value={tradeDate}
        placeholder="默认最近交易日"
        allowClear
        size="small"
        onChange={(value) => setState((prev) => ({ ...prev, tradeDate: value, page: 1 }))}
      />
      <Table<ApiPaperTradeOrder>
        size="small"
        rowKey="clOrdId"
        columns={orderColumns}
        dataSource={query.data?.items ?? []}
        loading={query.isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: query.data?.total ?? 0,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 条`,
          size: 'small',
          onChange: (next) => setState((prev) => ({ ...prev, page: next })),
        }}
        scroll={{ x: 1010 }}
      />
    </div>
  )
}

/** 成交列表（默认最近交易日）。 */
export function PaperTradeExecutionsPanel({ accountId }: { accountId: number }) {
  const [{ tradeDate, page }, setState] = useState<HistoryState>({
    tradeDate: null,
    page: 1,
  })
  const query = usePaperTradeExecutions(
    accountId,
    tradeDate ? tradeDate.format('YYYY-MM-DD') : undefined,
    page,
    PAGE_SIZE,
  )

  return (
    <div className="space-y-3">
      <DatePicker
        value={tradeDate}
        placeholder="默认最近交易日"
        allowClear
        size="small"
        onChange={(value) => setState((prev) => ({ ...prev, tradeDate: value, page: 1 }))}
      />
      <Table<ApiPaperTradeExecution>
        size="small"
        rowKey="execId"
        columns={executionColumns}
        dataSource={query.data?.items ?? []}
        loading={query.isLoading}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: query.data?.total ?? 0,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 条`,
          size: 'small',
          onChange: (next) => setState((prev) => ({ ...prev, page: next })),
        }}
        scroll={{ x: 760 }}
      />
    </div>
  )
}
