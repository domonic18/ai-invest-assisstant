import type { ApiNewsStats } from '@ai-invest/shared'

/** 今日资讯全局统计条：入库量 / AI 分级完成度 / 高重要度。 */
export function GlobalStatsBar({ stats }: { stats?: ApiNewsStats }) {
  if (!stats) return null
  const scoredPct =
    stats.todayTotal > 0
      ? Math.round((stats.scoredCount / stats.todayTotal) * 100)
      : 100
  return (
    <div className="flex items-center gap-5 flex-wrap rounded-lg border border-white/10 bg-white/[0.02] px-4 py-2.5 text-xs">
      <span className="opacity-70">
        今日入库 <b className="font-mono text-sm">{stats.todayTotal}</b> 条
      </span>
      <span className="w-px h-3.5 bg-white/10" />
      <span className="opacity-70">
        AI 分级{' '}
        <b className="font-mono text-sm">
          {stats.scoredCount}/{stats.todayTotal}
        </b>
        （{scoredPct}%）
      </span>
      <span className="w-px h-3.5 bg-white/10" />
      <span className="opacity-70">
        高重要度 <b className="font-mono text-sm text-red-500">{stats.highCount}</b>
      </span>
    </div>
  )
}
