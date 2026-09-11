import { useEffect, useState } from 'react'
import { Alert, Card, Skeleton, Tag, Typography } from 'antd'
import { Link, useParams } from 'react-router-dom'

import type {
  ApiSectorKlineBar,
  AnomalySectorType,
  StockKlineBar,
} from '@ai-invest/shared'

import { SourceNote } from '@/components/common/SourceNote'
import { useSectorDetail } from '@/hooks/useAnomaly'
import { changeColor, formatAmount, formatNumber, formatPercent } from '@/utils/formatters'

import { AnomalySidePanel } from './AnomalySidePanel'
import { FundFlowChart } from './FundFlowChart'
import { SectorChartArea } from './SectorChartArea'

/** 异动日竖线标注最多展示条数（过多会互相压盖）。 */
const MAX_MARKERS = 10

/** 异动栏收起态记忆（与个股详情右栏同样的持久化约定）。 */
const PANEL_COLLAPSED_KEY = 'ai-invest.sector-detail.anomaly-panel.collapsed'

function SnapshotStat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="text-sm font-medium truncate">{children}</span>
    </div>
  )
}

export function SectorDetailPage() {
  const { sectorType, sectorCode } = useParams<{
    sectorType: AnomalySectorType
    sectorCode: string
  }>()
  const { data, isLoading } = useSectorDetail(
    sectorType ?? 'industry',
    sectorCode ?? '',
  )
  const [panelCollapsed, setPanelCollapsed] = useState(
    () => localStorage.getItem(PANEL_COLLAPSED_KEY) === '1',
  )

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_COLLAPSED_KEY, panelCollapsed ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  }, [panelCollapsed])

  if (isLoading) {
    return (
      <Card variant="borderless">
        <Skeleton active paragraph={{ rows: 10 }} />
      </Card>
    )
  }
  if (!data) {
    return (
      <Card variant="borderless">
        <Alert
          type="warning"
          showIcon
          message="该板块暂无同花顺指数 K 线"
          description={
            <span>
              该东财板块未与同花顺板块同名覆盖（东财二/三级板块大多无对应指数），
              暂不展示走势。{' '}
              <Link to="/anomaly/sector" className="text-blue-400">
                返回板块异动榜
              </Link>
            </span>
          }
        />
      </Card>
    )
  }

  // THS 指数 K 线保证 OHLC 齐全；脏行防御性过滤后映射为通用 K 线结构
  const klineBars: StockKlineBar[] = data.bars
    .filter(
      (b): b is ApiSectorKlineBar & { open: number; high: number; low: number } =>
        b.open != null && b.high != null && b.low != null,
    )
    .map((b) => ({
      date: b.tradeDate,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
      volume: b.volume ?? 0,
      amount: b.amount ?? 0,
      changePct: b.changePct,
      amplitude: null,
      turnoverRate: null,
    }))
  const markers = [...data.anomalyDays]
    .sort((a, b) => b.tradeDate.localeCompare(a.tradeDate))
    .slice(0, MAX_MARKERS)
    .map((day) => ({ date: day.tradeDate, label: day.tradeDate.slice(5) }))
  const hasFundFlow = data.fundFlow.some(
    (p) => p.mainNetInflow != null || p.superLargeNet != null,
  )

  return (
    <div className="space-y-4">
      <Card
        variant="borderless"
        title={
          <div className="flex items-center gap-2 flex-wrap">
            <Typography.Text className="text-base font-semibold">
              {data.sectorName}
            </Typography.Text>
            <span className="text-xs text-gray-500 font-mono">{data.sectorCode}</span>
            <Tag className="!mr-0">{data.sectorType === 'concept' ? '概念' : '行业'}</Tag>
            <Tag color="gold" className="!mr-0">
              同花顺指数 K 线
            </Tag>
          </div>
        }
        extra={
          <Link to="/anomaly/sector" className="text-xs text-blue-400">
            返回板块异动榜
          </Link>
        }
      >
        {data.snapshot && (
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
            <SnapshotStat label={`收盘 ${data.snapshot.tradeDate}`}>
              <span className={changeColor(data.snapshot.changePct)}>
                {data.snapshot.close != null ? formatNumber(data.snapshot.close) : '-'}
                {data.snapshot.changePct != null && (
                  <span className="ml-1.5">{formatPercent(data.snapshot.changePct)}</span>
                )}
              </span>
            </SnapshotStat>
            <SnapshotStat label="成交额">
              {data.snapshot.amount != null ? formatAmount(data.snapshot.amount) : '-'}
            </SnapshotStat>
            <SnapshotStat label="换手率">
              {data.snapshot.turnoverRate != null
                ? `${data.snapshot.turnoverRate.toFixed(2)}%`
                : '-'}
            </SnapshotStat>
            <SnapshotStat label="涨/跌家数">
              <span className="font-mono text-xs">
                <span className="text-red-400">{data.snapshot.upCount ?? '-'}</span>
                <span className="text-gray-600"> / </span>
                <span className="text-green-400">{data.snapshot.downCount ?? '-'}</span>
              </span>
            </SnapshotStat>
            <SnapshotStat label="领涨股">{data.snapshot.leaderStockName ?? '-'}</SnapshotStat>
          </div>
        )}
      </Card>

      <div className="flex flex-col lg:flex-row gap-3 items-stretch">
        <div className="flex-1 min-w-0 space-y-3">
          <SectorChartArea bars={klineBars} markers={markers} />
          {hasFundFlow && (
            <Card
              variant="borderless"
              title={
                <Typography.Text className="text-sm font-semibold">
                  资金流向
                  <span className="ml-2 text-xs text-gray-500 font-normal">
                    四档单型净额 · 主力净流入累计
                  </span>
                </Typography.Text>
              }
              styles={{ body: { padding: '8px 8px 4px' } }}
            >
              <FundFlowChart points={data.fundFlow} />
            </Card>
          )}
          <SourceNote>
            K 线来源：同花顺板块指数（按板块名与东财体系桥接，周 K 由日 K 聚合）
            · 资金与异动标注为东财口径 · 异动日为竖线标注（金黃虚线）· 走势仅供研判异动合理性，非投资建议
          </SourceNote>
        </div>
        <AnomalySidePanel
          anomalyDays={data.anomalyDays}
          collapsed={panelCollapsed}
          onToggleCollapsed={() => setPanelCollapsed((v) => !v)}
        />
      </div>
    </div>
  )
}
