import { Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type {
  MarketReview,
  MarketStats,
  ReviewDayStatusItem,
  ReviewStatus,
  WorkbenchWatchlistGroup,
} from '@ai-invest/shared'

import { FoldCard } from './FoldCard'

interface ReviewStatusCardProps {
  status?: ReviewStatus | null
  review?: MarketReview | null
  groups?: WorkbenchWatchlistGroup[]
  stats?: MarketStats
  loading?: boolean
  className?: string
  stretch?: boolean
}

const DOT_CLASS: Record<ReviewStatus['status'], string> = {
  done: 'bg-green-500 ring-4 ring-green-500/10',
  pending: 'bg-amber-500 ring-4 ring-amber-500/10',
  failed: 'bg-red-500 ring-4 ring-red-500/10',
}

const TITLE: Record<ReviewStatus['status'], string> = {
  done: '今日复盘已生成',
  pending: '今日复盘待生成',
  failed: '今日复盘生成失败',
}

function dayMarkClass(day: ReviewDayStatusItem, isToday: boolean): string {
  if (day.status === 'success') return 'bg-green-400/10 text-green-400'
  if (day.status === 'failed') return 'bg-red-400/10 text-red-400'
  return isToday ? 'bg-amber-400/10 text-amber-400' : 'bg-gray-500/10 text-gray-500'
}

function dayMarkText(day: ReviewDayStatusItem): string {
  if (day.status === 'success') return '✓'
  if (day.status === 'failed') return '✕'
  return '…'
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m${s}s` : `${s}s`
}

function formatCountdown(nextRunAt: string): string {
  const minutes = dayjs(nextRunAt).diff(dayjs(), 'minute')
  if (minutes <= 0) return '即将开始'
  const h = Math.floor(minutes / 60)
  return h > 0 ? `距开始约 ${h} 小时 ${minutes % 60} 分` : `距开始约 ${minutes} 分钟`
}

function emotionChips(stats?: MarketStats) {
  const chips: { label: string; value: string }[] = []
  if (stats?.limitUpCount != null) chips.push({ label: '涨停', value: String(stats.limitUpCount) })
  if (stats?.limitDownCount != null)
    chips.push({ label: '跌停', value: String(stats.limitDownCount) })
  if (stats?.brokenLimitCount != null)
    chips.push({ label: '炸板', value: String(stats.brokenLimitCount) })
  if (stats?.limitUpRatio != null)
    chips.push({ label: '涨停比', value: `${stats.limitUpRatio}%` })
  if (stats?.continuousRate != null)
    chips.push({ label: '连板率', value: `${(stats.continuousRate * 100).toFixed(1)}%` })
  if (stats?.emotionScore != null)
    chips.push({ label: '情绪温度', value: `${stats.emotionScore.toFixed(0)}°` })
  return chips
}

function stockSummary(groups?: WorkbenchWatchlistGroup[]): string {
  const enabled = (groups ?? []).filter((g) => g.aiReviewEnabled)
  const total = enabled.reduce((sum, g) => sum + g.items.length, 0)
  if (total === 0) return '-'
  const ready = enabled.reduce(
    (sum, g) => sum + g.items.filter((i) => i.aiStatus === 'ready').length,
    0,
  )
  return `${ready}/${total}`
}

const TODAY = dayjs().format('YYYY-MM-DD')

/** 复盘状态卡：只呈现"做没做 / 何时做 / 做得怎样"，正文引流到每日复盘页。 */
export function ReviewStatusCard({
  status,
  review,
  groups,
  stats,
  loading,
  className,
  stretch,
}: ReviewStatusCardProps) {
  const chips = emotionChips(stats)

  const subtitle = (() => {
    if (!status) return '等待采集引擎数据'
    if (status.status === 'done') {
      const parts = [
        `AI · ${status.generatedAt ? dayjs(status.generatedAt).format('HH:mm') : '--'} 生成`,
      ]
      if (status.durationSeconds != null) parts.push(`耗时 ${formatDuration(status.durationSeconds)}`)
      if (review?.edited) parts.push('已人工编辑')
      return parts.join(' · ')
    }
    if (status.status === 'pending') {
      return status.plannedTime
        ? `计划 ${status.plannedTime} 自动运行 · ${formatCountdown(status.nextRunAt ?? '')}`
        : '等待采集引擎调度'
    }
    return '引擎将按计划自动重试，可在复盘页查看最近成功版本'
  })()

  return (
    <FoldCard
      title={
        <span>
          复盘状态
          {status && (
            <Tag color={status.status === 'done' ? 'success' : status.status === 'failed' ? 'error' : 'warning'} className="ml-2">
              {TITLE[status.status]}
            </Tag>
          )}
        </span>
      }
      extra={
        <Link to="/review" className="text-xs">
          {status?.status === 'done' ? '查看完整复盘' : '查看复盘页'}
        </Link>
      }
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : !status ? (
        <div className="text-xs text-gray-500 py-6 text-center">暂无复盘状态数据</div>
      ) : (
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-[#181a21] border border-gray-800">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className={`shrink-0 w-2.5 h-2.5 rounded-full ${DOT_CLASS[status.status]}`} />
              <div className="min-w-0">
                <div className="text-sm font-semibold text-gray-100">{TITLE[status.status]}</div>
                <div className="text-[11px] text-gray-500 mt-0.5 truncate">{subtitle}</div>
              </div>
            </div>
            <Link to="/review">
              <span className="shrink-0 text-xs text-[#8b93e8]">进入复盘 →</span>
            </Link>
          </div>

          {status.recentDays.length > 0 && (
            <div className="flex gap-4 mt-3.5 p-2.5 rounded-lg bg-[#181a21] border border-gray-800 overflow-x-auto">
              {status.recentDays.map((day) => {
                const isToday = day.tradeDate === TODAY
                return (
                  <div key={day.tradeDate} className="flex flex-col items-center gap-1">
                    <span className="text-[11px] text-gray-400 font-mono">
                      {day.tradeDate.slice(5)}
                    </span>
                    <span
                      className={`w-[18px] h-[18px] rounded-full flex items-center justify-center text-[10px] font-bold ${dayMarkClass(day, isToday)}`}
                    >
                      {dayMarkText(day)}
                    </span>
                    {isToday && <span className="text-[10px] text-amber-400">今日</span>}
                  </div>
                )
              })}
            </div>
          )}

          <div className="grid grid-cols-3 gap-2.5 mt-3.5">
            <div className="rounded-lg bg-[#181a21] border border-gray-800 px-3 py-2.5 text-center">
              <div className="text-lg font-bold font-mono text-gray-100">{status.streakDays}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">连续生成天数</div>
            </div>
            <div className="rounded-lg bg-[#181a21] border border-gray-800 px-3 py-2.5 text-center">
              <div className="text-lg font-bold font-mono text-gray-100">{stockSummary(groups)}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">自选股点评已生成</div>
            </div>
            <div className="rounded-lg bg-[#181a21] border border-gray-800 px-3 py-2.5 text-center">
              <div className="text-lg font-bold font-mono text-gray-100">
                {status.monthSuccessRate != null ? `${status.monthSuccessRate}%` : '-'}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">本月生成成功率</div>
            </div>
          </div>

          {chips.length > 0 && (
            <div className="flex gap-2 flex-wrap mt-3.5 pt-3.5 border-t border-gray-800">
              {chips.map((chip) => (
                <span
                  key={chip.label}
                  className="text-[11px] px-2.5 py-0.5 rounded-full bg-[#181a21] border border-gray-800 text-gray-400"
                >
                  {chip.label} <b className="text-gray-100 font-mono">{chip.value}</b>
                </span>
              ))}
            </div>
          )}

          <div className="flex-1" />
          <div className="pt-2.5 text-[10px] text-gray-600 border-t border-dashed border-gray-800">
            复盘正文与分时归因在「每日复盘」页查看；工作台仅呈现状态与统计
          </div>
        </div>
      )}
    </FoldCard>
  )
}
