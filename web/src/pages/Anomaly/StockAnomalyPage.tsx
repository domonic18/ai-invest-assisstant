import { Button, Card, DatePicker, Empty, Select, Skeleton, Table, Tag, Tooltip, Typography } from 'antd'
import { StarFilled } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { PAGE_EVENT_TYPES, type ApiStockAnomalyItem } from '@ai-invest/shared'

import { SourceNote } from '@/components/common/SourceNote'
import { useStockAnomalyBoard } from '@/hooks/useAnomaly'
import { useAssistantStore } from '@/stores/assistant'
import { useColorScheme } from '@/stores/settings'
import { changeColor, DATE_FORMAT, formatNumber, formatPercent } from '@/utils/formatters'

import { AttributionCell, AnomalyTypeTags, STOCK_CATEGORY_LABELS } from './cells'
import { ANOMALY_TYPE_LABELS } from './labels'
import { stockAttributionPrompt } from './attributionPrompts'
import { useAnomalyAttribution } from './useAnomalyAttribution'

export function StockAnomalyPage() {
  useColorScheme()
  const [tradeDate, setTradeDate] = useState<string>()
  const [typeFilter, setTypeFilter] = useState<string>()

  const { data, isLoading } = useStockAnomalyBoard(tradeDate)

  const generating = useAnomalyAttribution(PAGE_EVENT_TYPES.stockAnomaly)

  const typeOptions = useMemo(
    () =>
      Array.from(new Set((data?.items ?? []).flatMap((it) => it.anomalyTypes)))
        .sort()
        .map((t) => ({ label: ANOMALY_TYPE_LABELS[t] ?? t, value: t })),
    [data],
  )

  const items = useMemo(() => {
    const rows = data?.items ?? []
    return typeFilter ? rows.filter((it) => it.anomalyTypes.includes(typeFilter)) : rows
  }, [data, typeFilter])

  // 页面级归因：强度榜前 20 条打包为一份目标清单发给助手
  const handleGenerateAll = () => {
    const targets = (data?.items ?? []).slice(0, 20)
    if (targets.length === 0) return
    useAssistantStore.getState().sendQuestion(stockAttributionPrompt(data?.tradeDate, targets))
  }

  const handleGenerateRow = (item: ApiStockAnomalyItem) => {
    useAssistantStore.getState().sendQuestion(stockAttributionPrompt(data?.tradeDate, [item]))
  }

  const columns: ColumnsType<ApiStockAnomalyItem> = [
    {
      title: '个股',
      dataIndex: 'stockName',
      fixed: 'left',
      width: 170,
      render: (_, it) => (
        <div className="flex items-center gap-1.5 min-w-0">
          <Link to={`/stock/${it.stockCode}`} className="font-medium truncate hover:underline">
            {it.stockName}
          </Link>
          {it.isWatchlist && (
            <Tooltip title="命中自选">
              <StarFilled className="text-yellow-500 text-xs shrink-0" />
            </Tooltip>
          )}
          <span className="text-xs text-gray-500 font-mono shrink-0">{it.stockCode}</span>
        </div>
      ),
    },
    {
      title: '收盘',
      dataIndex: 'close',
      width: 80,
      align: 'right',
      render: (v: number | null) => (v != null ? formatNumber(v) : '-'),
    },
    {
      title: '涨跌幅',
      dataIndex: 'changePct',
      width: 90,
      align: 'right',
      sorter: (a, b) => (a.changePct ?? 0) - (b.changePct ?? 0),
      render: (v: number | null) => (
        <span className={`font-medium ${changeColor(v)}`}>
          {v != null ? formatPercent(v) : '-'}
        </span>
      ),
    },
    {
      title: '换手率',
      dataIndex: 'turnoverRate',
      width: 85,
      align: 'right',
      sorter: (a, b) => (a.turnoverRate ?? 0) - (b.turnoverRate ?? 0),
      render: (v: number | null) =>
        v != null ? <span className="font-mono">{v.toFixed(2)}%</span> : '-',
    },
    {
      title: '量比',
      dataIndex: 'volumeRatio',
      width: 80,
      align: 'right',
      sorter: (a, b) => (a.volumeRatio ?? 0) - (b.volumeRatio ?? 0),
      render: (v: number | null) =>
        v != null ? <span className="font-mono">{v.toFixed(2)}x</span> : '-',
    },
    {
      title: 'MA60',
      key: 'ma60',
      width: 130,
      render: (_, it) => (
        <Tooltip
          title={it.ma60 != null ? `MA60 ${formatNumber(it.ma60)}` : 'MA60 数据不足，未判定'}
        >
          <span className="flex items-center gap-1">
            {it.ma60Breakout && (
              <Tag color="red" className="!mr-0">
                突破
              </Tag>
            )}
            <span
              className={`text-xs ${
                it.isAboveMa60 ? 'text-red-400' : 'text-green-400'
              }`}
            >
              {it.isAboveMa60 ? '线上' : '线下'}
            </span>
          </span>
        </Tooltip>
      ),
    },
    {
      title: '异动类型',
      dataIndex: 'anomalyTypes',
      width: 180,
      render: (types: string[]) => <AnomalyTypeTags types={types} />,
    },
    {
      title: '强度',
      dataIndex: 'strength',
      width: 70,
      align: 'right',
      defaultSortOrder: 'descend',
      sorter: (a, b) => a.strength - b.strength,
      render: (v: number) => <span className="font-semibold font-mono">{v}</span>,
    },
    {
      title: 'AI 归因',
      key: 'attribution',
      render: (_, it) => (
        <AttributionCell
          category={it.attributionCategory}
          summary={it.attributionSummary}
          labels={STOCK_CATEGORY_LABELS}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      fixed: 'right',
      render: (_, it) => (
        <Button type="link" size="small" className="!px-0" onClick={() => handleGenerateRow(it)}>
          AI 归因
        </Button>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <Card
        variant="borderless"
        title={
          <Typography.Text className="text-base font-semibold">个股异动榜</Typography.Text>
        }
      >
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <DatePicker
            allowClear
            placeholder="最近检测日"
            value={tradeDate ? dayjs(tradeDate) : null}
            onChange={(d: Dayjs | null) => {
              setTradeDate(d ? d.format(DATE_FORMAT) : undefined)
            }}
          />
          <Select
            allowClear
            placeholder="异动类型"
            style={{ width: 140 }}
            options={typeOptions}
            value={typeFilter}
            onChange={(v) => setTypeFilter(v)}
          />
          <span className="ml-auto flex items-center gap-3">
            <span className="text-xs text-gray-500">
              {data?.tradeDate ? `${data.tradeDate} · ` : ''}
              {items.length} 条
            </span>
            <Button
              type="primary"
              ghost
              size="small"
              loading={generating}
              disabled={items.length === 0}
              onClick={handleGenerateAll}
            >
              {generating ? 'AI 归因中，请留意侧边栏助手…' : 'AI 归因 Top20'}
            </Button>
          </span>
        </div>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 10 }} />
        ) : !data || data.total === 0 ? (
          <Empty description="暂无异动数据，等待盘后检测任务执行" />
        ) : (
          <Table
            rowKey="stockCode"
            columns={columns}
            dataSource={items}
            size="small"
            scroll={{ x: 1150 }}
            pagination={{ pageSize: 50, hideOnSinglePage: true, showSizeChanger: false }}
          />
        )}
        <SourceNote>
          规则检测：MA60 趋势 + 量价维度 · 强度为命中维度加权得分 · ★ 为命中自选 · AI 归因摘要仅供参考
        </SourceNote>
      </Card>
    </div>
  )
}
