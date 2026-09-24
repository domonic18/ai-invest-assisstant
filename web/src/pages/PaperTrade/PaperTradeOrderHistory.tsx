import { DatePicker, Table, Tabs, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import type {
  ApiPaperTradeExecution,
  ApiPaperTradeOrder,
} from '@ai-invest/shared'

import { usePaperTradeExecutions, usePaperTradeOrders } from '@/hooks/usePaperTrade'
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

const PAGE_SIZE = 20

function sideCell(side: number | null | undefined) {
  if (side === 1) return <span style={{ color: riseColor() }}>买入</span>
  if (side === 2) return <span style={{ color: fallColor() }}>卖出</span>
  return '-'
}

/** 6 位代码优先；回报 wire 无 stockCode 时从掘金 symbol 取点号后段。 */
function stockCell(record: { stockCode?: string | null; symbol: string }) {
  if (record.stockCode) return record.stockCode
  const symbol = record.symbol || ''
  return symbol.includes('.') ? symbol.split('.')[1] : symbol
}

const orderColumns: ColumnsType<ApiPaperTradeOrder> = [
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

function OrdersTab() {
  const [{ tradeDate, page }, setState] = useState<HistoryState>({
    tradeDate: null,
    page: 1,
  })
  const query = usePaperTradeOrders(
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
        scroll={{ x: 860 }}
      />
    </div>
  )
}

function ExecutionsTab() {
  const [{ tradeDate, page }, setState] = useState<HistoryState>({
    tradeDate: null,
    page: 1,
  })
  const query = usePaperTradeExecutions(
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

export function PaperTradeOrderHistory() {
  return (
    <Tabs
      defaultActiveKey="orders"
      items={[
        { key: 'orders', label: '委托', children: <OrdersTab /> },
        { key: 'executions', label: '成交', children: <ExecutionsTab /> },
      ]}
    />
  )
}
