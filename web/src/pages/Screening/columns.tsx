import type { ColumnsType } from 'antd/es/table'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type { StockScreeningRow } from '@/stores/assistant'
import { changeColor, formatAmount, formatPercent } from '@/utils/formatters'

/** 已知中文列的渲染与宽度映射；未命中列走纯文本兜底（问句变了表格不崩）。 */

function asNumber(value: unknown): number | null {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function renderText(value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

function renderPrice(value: unknown): ReactNode {
  const n = asNumber(value)
  return n === null ? '-' : n.toFixed(2)
}

function renderChangePct(value: unknown): ReactNode {
  const n = asNumber(value)
  if (n === null) return '-'
  return <span className={changeColor(n)}>{formatPercent(n)}</span>
}

function renderPercent(value: unknown): ReactNode {
  const n = asNumber(value)
  return n === null ? '-' : `${n.toFixed(2)}%`
}

function renderAmount(value: unknown): ReactNode {
  const n = asNumber(value)
  return n === null ? '-' : formatAmount(n)
}

const COLUMN_RENDERERS: Record<string, (value: unknown) => ReactNode> = {
  最新价: renderPrice,
  涨跌幅: renderChangePct,
  换手率: renderPercent,
  成交额: renderAmount,
}

const COLUMN_WIDTHS: Record<string, number> = {
  最新价: 90,
  涨跌幅: 90,
  换手率: 90,
  成交额: 110,
}

function compareByColumn(a: StockScreeningRow, b: StockScreeningRow, key: string): number {
  const na = asNumber(a[key])
  const nb = asNumber(b[key])
  if (na !== null && nb !== null) return na - nb
  return String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'zh-CN')
}

export function buildScreeningColumns(columns: string[]): ColumnsType<StockScreeningRow> {
  return [
    { title: '代码', dataIndex: 'stockCode', key: 'stockCode', width: 90, fixed: 'left' },
    {
      title: '名称',
      dataIndex: 'stockName',
      key: 'stockName',
      width: 110,
      fixed: 'left',
      ellipsis: true,
      render: (name: unknown, row) => (
        <Link to={`/stock/${encodeURIComponent(row.stockCode)}`}>
          {renderText(name)}
        </Link>
      ),
    },
    ...columns.map((column) => ({
      title: column,
      dataIndex: column,
      key: column,
      width: COLUMN_WIDTHS[column] ?? 120,
      ellipsis: true,
      sorter: (a: StockScreeningRow, b: StockScreeningRow) => compareByColumn(a, b, column),
      render: (value: unknown) => (COLUMN_RENDERERS[column] ?? renderText)(value),
    })),
  ]
}
