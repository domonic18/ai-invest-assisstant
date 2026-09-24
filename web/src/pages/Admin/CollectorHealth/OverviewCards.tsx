import type { ReactNode } from 'react'

import type { ApiCollectorHealthOverview, ApiCollectorHealthTaskItem } from '@ai-invest/shared'

import { rateText } from './constants'

interface OverviewCardsProps {
  overview: ApiCollectorHealthOverview
  tasks: ApiCollectorHealthTaskItem[]
}

interface StatCardProps {
  label: string
  value: ReactNode
  valueColor?: string
  dotColor?: string
  foot?: ReactNode
}

/** 统计卡：label + 大数字 + foot 上下文行（原型 stat-card 结构）。 */
export function OverviewCards({ overview, tasks }: OverviewCardsProps) {
  const { healthScore, counts, successRate24h } = overview
  const overdue = tasks.filter((t) => t.windowsWithoutSuccess > 0)
  const overdueWindows = overdue.reduce((sum, t) => sum + t.windowsWithoutSuccess, 0)
  const judgeable = overview.total - counts.paused - counts.unconfigured
  const scoreColor = healthScore >= 90 ? '#2ea043' : healthScore >= 60 ? '#d29922' : '#f85149'
  const faultCount = counts.critical + counts.silent

  return (
    <div className="grid grid-cols-2 gap-3.5 md:grid-cols-3 xl:grid-cols-5">
      <StatCard
        label="整体健康分"
        value={healthScore}
        valueColor={scoreColor}
        dotColor={scoreColor}
        foot={
          <span>
            {counts.healthy} 健康 · {counts.degraded} 观察 / {judgeable} 可判定
          </span>
        }
      />
      <StatCard
        label="进行中故障"
        value={faultCount}
        valueColor={faultCount > 0 ? '#f85149' : undefined}
        dotColor={faultCount > 0 ? '#f85149' : '#2ea043'}
        foot={
          <span>
            critical {counts.critical} · silent {counts.silent}
          </span>
        }
      />
      <StatCard
        label="降级观察"
        value={counts.degraded}
        valueColor={counts.degraded > 0 ? '#d29922' : undefined}
        dotColor={counts.degraded > 0 ? '#d29922' : '#2ea043'}
        foot={<span>成功率 / 连败 / 产出停滞</span>}
      />
      <StatCard
        label="脱期任务"
        value={overdue.length}
        valueColor={overdue.length > 0 ? '#f85149' : undefined}
        dotColor={overdue.length > 0 ? '#f85149' : '#2ea043'}
        foot={<span>缺口窗口合计 {overdueWindows}</span>}
      />
      <StatCard
        label="24h 成功率"
        value={rateText(successRate24h)}
        valueColor={successRate24h != null && successRate24h < 0.8 ? '#d29922' : '#2ea043'}
        dotColor={successRate24h != null && successRate24h < 0.8 ? '#d29922' : '#2ea043'}
        foot={<span>skipped 剔除口径</span>}
      />
    </div>
  )
}

function StatCard({ label, value, valueColor, dotColor, foot }: StatCardProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-2 text-xs text-gray-400">{label}</div>
      <div className="text-[26px] font-bold leading-8 tracking-tight" style={{ color: valueColor }}>
        {value}
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-400">
        {dotColor && (
          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: dotColor }} />
        )}
        {foot}
      </div>
    </div>
  )
}
