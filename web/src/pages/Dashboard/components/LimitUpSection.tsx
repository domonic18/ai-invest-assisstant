import { Card, Skeleton, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'

import type { LimitUpData, LimitUpStock } from '@ai-invest/shared'
import { SourceNote } from '@/components/common/SourceNote'
import { useColorScheme } from '@/stores/settings'
import {
  changeColor,
  changeHex,
  formatAmount,
  formatPercent,
  formatSealTime,
} from '@/utils/formatters'

interface LimitUpSectionProps {
  data?: LimitUpData
  loading: boolean
  /** 查看的是当日且尚未收盘（涨停池收盘后才写入）。 */
  pendingClose?: boolean
  /** 查看的是历史日期，可通过右上角按钮补采。 */
  canBackfill?: boolean
}

const BOARD_COLORS: Record<number, string> = {
  6: '#f85149',
  5: '#d29922',
  4: '#d29922',
}

function boardColor(boards: number): string {
  return BOARD_COLORS[boards] ?? '#5e6ad2'
}

function SealBadge({ item }: { item: LimitUpStock }) {
  const boards = item.consecutiveBoards ?? 0
  const boardText = boards >= 2 ? `${boards}板` : '首板'
  const prefix = item.sealType === '一字板' ? '一字' : item.sealType === 'T字板' ? 'T' : null
  const color = prefix ? '#f85149' : boardColor(boards)
  return (
    <span
      className="rounded px-1.5 py-0.5 text-xs font-bold text-white whitespace-nowrap"
      style={{ background: color }}
    >
      {prefix ? `${prefix}·${boardText}` : boardText}
    </span>
  )
}

export function LimitUpSection({ data, loading, pendingClose, canBackfill }: LimitUpSectionProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }
  if (!data || data.total === 0) {
    const emptyText = pendingClose
      ? '今日还未收盘，涨停与连板数据将在收盘后更新'
      : canBackfill
        ? '暂无涨停数据，可点击右上角「补采数据」获取该日历史数据'
        : '暂无涨停数据，等待采集任务执行'
    return (
      <Card variant="borderless" title="连板天梯">
        <div className="text-gray-500 text-sm">{emptyText}</div>
      </Card>
    )
  }

  return (
    <>
      <Card
        variant="borderless"
        title="连板天梯"
        extra={<span className="text-xs text-gray-500">当日最高 {data.maxBoards ?? '-'} 板</span>}
      >
        <div className="space-y-1.5">
          {data.ladder.map((item) => {
            const boards = item.consecutiveBoards ?? 0
            return (
              <div
                key={item.stockCode}
                className="flex items-center gap-3 rounded px-2 py-1.5 bg-[#1a1d24]"
                style={{ borderLeft: `3px solid ${boardColor(boards)}` }}
              >
                <span
                  className="w-6 h-6 rounded text-center leading-6 text-xs font-bold text-white"
                  style={{ background: boardColor(boards) }}
                >
                  {boards}
                </span>
                <Link to={`/stock/${item.stockCode}`} className="flex-1 font-medium">
                  {item.stockName}
                </Link>
                <span className="font-mono text-xs text-gray-500">{item.stockCode}</span>
                <Tag color="default">{item.industry ?? '未分类'}</Tag>
                <span className={`text-sm font-medium ${changeColor(item.changePct)}`}>
                  {item.changePct != null ? formatPercent(item.changePct) : '-'}
                </span>
              </div>
            )
          })}
        </div>
        <SourceNote>
          东方财富 · 仅展示 ≥2 板个股 · 涨停 {data.total} 家 · 首板 {data.firstBoard} · 连板 {data.continuous}
        </SourceNote>
      </Card>

      <Card
        variant="borderless"
        title="涨停复盘"
        extra={
          <span className="text-xs text-gray-400">
            共 {data.total} 只涨停 · 首板 {data.firstBoard} · 连板 {data.continuous}
          </span>
        }
      >
        <div className="space-y-4">
          {data.groups.map((group) => (
            <div key={group.industry}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded bg-red-500/10 px-2.5 py-1.5 mb-2">
                <span className="text-sm font-semibold text-red-400">{group.industry}</span>
                {group.changePct != null && (
                  <span className="text-xs font-medium" style={{ color: changeHex(group.changePct) }}>
                    {formatPercent(group.changePct)}
                  </span>
                )}
                {group.mainNetInflow != null && (
                  <span className="text-xs text-gray-400">
                    主力净流入 {formatAmount(group.mainNetInflow)}
                  </span>
                )}
                <span className="text-xs text-gray-500 ml-auto">{group.count} 家涨停</span>
              </div>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <div
                    key={item.stockCode}
                    className="flex items-center gap-2.5 rounded px-2 py-1.5 bg-[#1a1d24]"
                  >
                    <SealBadge item={item} />
                    <Link to={`/stock/${item.stockCode}`} className="font-medium text-sm">
                      {item.stockName}
                    </Link>
                    <span className="font-mono text-xs text-gray-500">{item.stockCode}</span>
                    <span className="font-mono text-xs text-gray-400">
                      {formatSealTime(item.firstSealTime)}
                    </span>
                    <Tag color="default" className="ml-auto">
                      {item.industry ?? '未分类'}
                    </Tag>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <SourceNote>
          东方财富涨停股池 · 按所属行业分组 · 板块涨跌幅/主力净流入来自板块资金流 ·
          一字=开盘涨停全天未开板，T=开盘涨停盘中打开后回封
        </SourceNote>
      </Card>
    </>
  )
}

export function LimitUpSectionTitle() {
  return (
    <Typography.Text className="text-gray-400 text-xs tracking-widest">
      涨停与连板
    </Typography.Text>
  )
}
