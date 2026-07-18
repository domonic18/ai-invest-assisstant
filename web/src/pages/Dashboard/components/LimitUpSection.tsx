import { Card, Skeleton, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'

import type { LimitUpData } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { changeColor, formatAmount, formatPercent } from '@/utils/formatters'

interface LimitUpSectionProps {
  data?: LimitUpData
  loading: boolean
}

const BOARD_COLORS: Record<number, string> = {
  6: '#f85149',
  5: '#d29922',
  4: '#d29922',
}

function boardColor(boards: number): string {
  return BOARD_COLORS[boards] ?? '#5e6ad2'
}

export function LimitUpSection({ data, loading }: LimitUpSectionProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }
  if (!data || data.total === 0) {
    return (
      <Card variant="borderless" title="连板天梯">
        <div className="text-gray-500 text-sm">暂无涨停数据，等待采集任务执行</div>
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
        <div className="mt-3 text-center text-xs text-gray-500">
          数据来源: 东方财富 · 仅展示 ≥2 板个股 · 涨停 {data.total} 家 · 首板 {data.firstBoard} · 连板 {data.continuous}
        </div>
      </Card>

      <Card
        variant="borderless"
        title="今日涨停板"
        extra={
          <span className="text-xs text-gray-400">
            共 {data.total} 只涨停 · 首板 {data.firstBoard} · 连板 {data.continuous}
          </span>
        }
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {data.items.map((item) => {
            const boards = item.consecutiveBoards ?? 0
            return (
              <Link
                key={item.stockCode}
                to={`/stock/${item.stockCode}`}
                className="rounded p-2 bg-[#1a1d24] hover:bg-[#22262f] transition-colors"
                style={boards >= 4 ? { borderLeft: `3px solid ${boardColor(boards)}` } : undefined}
              >
                <div className="text-sm font-medium text-gray-100">{item.stockName}</div>
                <div className="text-xs text-gray-500 font-mono">
                  {item.stockCode} · {boards >= 2 ? `${boards}板` : '首板'}
                </div>
                <div className="text-xs text-gray-400">
                  {item.industry ?? '未分类'}
                  {item.sealedAmount != null && (
                    <span className="ml-2">封单 {formatAmount(item.sealedAmount)}</span>
                  )}
                </div>
              </Link>
            )
          })}
        </div>
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
