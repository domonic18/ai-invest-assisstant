import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type { ReviewStatus, ReviewStatusState } from '@ai-invest/shared'

import { useReviewStatus } from '@/hooks/useWorkbench'

const DOT_CLASS: Record<ReviewStatusState, string> = {
  done: 'bg-green-500',
  pending: 'bg-amber-500',
  failed: 'bg-red-500',
}

const TITLE: Record<ReviewStatusState, string> = {
  done: '今日复盘已生成',
  pending: '今日复盘待生成',
  failed: '今日复盘生成失败',
}

function dayDotClass(status: string, isToday: boolean): string {
  if (status === 'success') return 'bg-green-400/70'
  if (status === 'failed') return 'bg-red-400/70'
  return isToday ? 'bg-amber-400/70' : 'bg-gray-600'
}

function subtitle(status: ReviewStatus): string {
  if (status.status === 'done') {
    return `AI · ${status.generatedAt ? dayjs(status.generatedAt).format('HH:mm') : '--'} 生成`
  }
  if (status.status === 'pending') {
    if (!status.plannedTime || !status.nextRunAt) return '等待采集引擎调度'
    const minutes = dayjs(status.nextRunAt).diff(dayjs(), 'minute')
    if (minutes <= 0) return `计划 ${status.plannedTime} 运行 · 即将开始`
    const h = Math.floor(minutes / 60)
    return `计划 ${status.plannedTime} 运行 · 距 ${h > 0 ? `${h} 小时 ` : ''}${minutes % 60} 分`
  }
  return '引擎将按计划自动重试'
}

/** 侧边栏复盘状态块（自工作台主区迁入）：状态点 + 近 5 日结果 + 复盘页入口。 */
export function SidebarReviewStatus() {
  const { data: status } = useReviewStatus()

  if (!status) return null

  const today = dayjs().format('YYYY-MM-DD')

  return (
    <div className="px-4 py-3 border-t border-gray-800 shrink-0">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-gray-500">复盘状态</span>
        <Link to="/review" className="text-[11px] text-[#8b93e8] hover:underline">
          进入复盘 →
        </Link>
      </div>
      <div className="flex items-center gap-2 mt-2 min-w-0">
        <span className={`shrink-0 w-2 h-2 rounded-full ${DOT_CLASS[status.status]}`} />
        <span className="text-xs text-gray-300 truncate">{TITLE[status.status]}</span>
      </div>
      <div className="text-[10px] text-gray-600 mt-1 truncate">{subtitle(status)}</div>
      {status.recentDays.length > 0 && (
        <div className="flex items-center gap-1.5 mt-2">
          {status.recentDays.map((day) => (
            <span
              key={day.tradeDate}
              title={`${day.tradeDate} ${day.status}`}
              className={`w-2 h-2 rounded-full ${dayDotClass(day.status, day.tradeDate === today)}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}
