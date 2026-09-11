import { Button, Card, DatePicker, Empty, Popconfirm, Segmented, Select, Skeleton, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  PAGE_EVENT_TYPES,
  type AnomalySectorType,
  type ApiSectorAnomalyItem,
} from '@ai-invest/shared'

import { SourceNote } from '@/components/common/SourceNote'
import { useSectorAnomalyBoard } from '@/hooks/useAnomaly'
import { useAssistantStore } from '@/stores/assistant'
import { useColorScheme } from '@/stores/settings'
import { changeColor, DATE_FORMAT, formatAmount, formatPercent } from '@/utils/formatters'

import { AttributionAction, AttributionCell, AnomalyTypeTags, SECTOR_CATEGORY_LABELS } from './cells'
import { ANOMALY_TYPE_LABELS } from './labels'
import { sectorAttributionPrompt } from './attributionPrompts'
import { useAnomalyAttribution } from './useAnomalyAttribution'

type SectorTypeFilter = AnomalySectorType | 'all'

const SECTOR_TYPE_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '行业', value: 'industry' },
  { label: '概念', value: 'concept' },
]

export function SectorAnomalyPage() {
  useColorScheme()
  const [tradeDate, setTradeDate] = useState<string>()
  const [sectorType, setSectorType] = useState<SectorTypeFilter>('all')
  const [typeFilter, setTypeFilter] = useState<string>()

  const { data, isLoading } = useSectorAnomalyBoard(
    tradeDate,
    sectorType === 'all' ? undefined : sectorType,
  )

  const generating = useAnomalyAttribution(PAGE_EVENT_TYPES.sectorAnomaly)

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

  const isAttributed = (it: ApiSectorAnomalyItem) =>
    Boolean(it.attributionCategory || it.attributionSummary)

  // 页面级归因目标：优先只补「未归因」缺口（强度榜前 10），避免对已有归因的
  // 条目重复生成；全部已归因时按钮转为显式「重新归因」（带覆盖确认）
  const missingTargets = useMemo(
    () => items.filter((it) => !isAttributed(it)).slice(0, 10),
    [items],
  )
  const regenerateTargets = useMemo(
    () => items.filter((it) => isAttributed(it)).slice(0, 10),
    [items],
  )

  const handleGenerate = (targets: ApiSectorAnomalyItem[]) => {
    if (targets.length === 0) return
    useAssistantStore.getState().sendQuestion(sectorAttributionPrompt(data?.tradeDate, targets))
  }

  const columns: ColumnsType<ApiSectorAnomalyItem> = [
    {
      title: '板块',
      key: 'sector',
      fixed: 'left',
      width: 200,
      render: (_, it) => (
        <div className="flex items-baseline gap-2 min-w-0">
          <Link
            to={`/sector/${it.sectorType}/${it.sectorCode}`}
            className="font-medium truncate hover:underline"
            title="查看板块 K 线详情"
          >
            {it.sectorName}
          </Link>
          <span className="text-xs text-gray-500 font-mono shrink-0">{it.sectorCode}</span>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'sectorType',
      width: 80,
      render: (v: string) => (v === 'concept' ? '概念' : '行业'),
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
      title: '成交额',
      dataIndex: 'amount',
      width: 90,
      align: 'right',
      render: (v: number | null) => (v != null ? formatAmount(v) : '-'),
    },
    {
      title: '放量倍数',
      dataIndex: 'amountRatio',
      width: 90,
      align: 'right',
      sorter: (a, b) => (a.amountRatio ?? 0) - (b.amountRatio ?? 0),
      render: (v: number | null) =>
        v != null ? <span className="font-mono">{v.toFixed(2)}x</span> : '-',
    },
    {
      title: '涨/跌家数',
      key: 'counts',
      width: 100,
      align: 'right',
      render: (_, it) => (
        <span className="font-mono text-xs">
          <span className="text-red-400">{it.upCount ?? '-'}</span>
          <span className="text-gray-600"> / </span>
          <span className="text-green-400">{it.downCount ?? '-'}</span>
        </span>
      ),
    },
    {
      title: '异动类型',
      dataIndex: 'anomalyTypes',
      width: 170,
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
          labels={SECTOR_CATEGORY_LABELS}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      fixed: 'right',
      render: (_, it) => (
        <AttributionAction
          attributed={isAttributed(it)}
          disabled={generating}
          onTrigger={() => handleGenerate([it])}
        />
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <Card
        variant="borderless"
        title={
          <Typography.Text className="text-base font-semibold">板块异动榜</Typography.Text>
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
          <Segmented
            options={SECTOR_TYPE_OPTIONS}
            value={sectorType}
            onChange={(v) => setSectorType(v as SectorTypeFilter)}
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
            {missingTargets.length > 0 ? (
              <Button
                type="primary"
                ghost
                size="small"
                loading={generating}
                onClick={() => handleGenerate(missingTargets)}
              >
                {generating
                  ? 'AI 归因中，请留意侧边栏助手…'
                  : `AI 归因（待归因 ${missingTargets.length} 条）`}
              </Button>
            ) : (
              <Popconfirm
                title="所选条目已全部有归因摘要"
                description="重新生成将覆盖现有结果，确定继续？"
                okText="重新归因"
                cancelText="取消"
                onConfirm={() => handleGenerate(regenerateTargets)}
              >
                <Button size="small" loading={generating} disabled={regenerateTargets.length === 0}>
                  重新归因 Top10
                </Button>
              </Popconfirm>
            )}
          </span>
        </div>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 10 }} />
        ) : !data || data.total === 0 ? (
          <Empty description="暂无异动数据，等待盘后检测任务执行" />
        ) : (
          <Table
            rowKey={(it) => `${it.sectorType}:${it.sectorCode}`}
            columns={columns}
            dataSource={items}
            size="small"
            scroll={{ x: 1100 }}
            pagination={{ pageSize: 50, hideOnSinglePage: true, showSizeChanger: false }}
          />
        )}
        <SourceNote>
          规则检测：MA60 趋势 + 量价维度 · 强度为命中维度加权得分 · 检测任务已自动归因强度榜前 10，页面按钮仅补齐缺失归因或显式重新归因 · 归因摘要仅供参考
        </SourceNote>
      </Card>
    </div>
  )
}
