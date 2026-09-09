import { Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import type { CollectorEngineStatus } from '@ai-invest/shared'

import { FoldCard } from './FoldCard'

interface CollectorEngineCardProps {
  status?: CollectorEngineStatus | null
  loading?: boolean
  className?: string
  stretch?: boolean
}

const RUN_DOT: Record<string, string> = {
  SUCCESS: 'bg-green-500',
  PARTIAL: 'bg-green-500',
  FAILED: 'bg-red-500',
  TIMEOUT: 'bg-red-500',
  SKIPPED: 'bg-gray-600',
}

function runDotClass(status: string): string {
  return RUN_DOT[status] ?? 'bg-amber-500'
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m${s}s` : `${s}s`
}

function formatElapsed(startedAt: string | null): string {
  if (!startedAt) return ''
  const seconds = Math.max(0, dayjs().diff(dayjs(startedAt), 'second'))
  return formatDuration(seconds)
}

/** 采集引擎状态卡：呈现"是否在跑 / 接下来跑什么 / 最近跑得怎样"。 */
export function CollectorEngineCard({
  status,
  loading,
  className,
  stretch,
}: CollectorEngineCardProps) {
  const [, setTick] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setTick((v) => v + 1), 30_000)
    return () => clearInterval(timer)
  }, [])

  return (
    <FoldCard
      title={
        <span className="inline-flex items-center gap-2">
          采集引擎
          {status && (
            <Tag color={status.isRunning ? 'success' : 'default'} className="!mr-0">
              {status.isRunning ? '运行中' : '空闲'}
            </Tag>
          )}
        </span>
      }
      extra={<Link to="/admin/tasks" className="text-xs">任务管理</Link>}
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : !status ? (
        <div className="text-xs text-gray-500 py-6 text-center">暂无采集引擎数据</div>
      ) : (
        <div className="flex flex-col h-full">
          {status.running ? (
            <div className="flex items-center gap-2.5 p-3 rounded-lg bg-[#181a21] border border-gray-800">
              <span className="relative flex w-2.5 h-2.5 shrink-0">
                <span className="absolute inline-flex w-full h-full rounded-full bg-green-400 opacity-60 animate-ping" />
                <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-green-500" />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-gray-100 truncate">
                  {status.running.taskLabel}
                </div>
                <div className="text-[11px] text-gray-500 mt-0.5">
                  {status.running.source ?? '-'} · 已运行 {formatElapsed(status.running.startedAt)}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2.5 p-3 rounded-lg bg-[#181a21] border border-gray-800">
              <span className="w-2.5 h-2.5 shrink-0 rounded-full bg-gray-600" />
              <div className="text-sm text-gray-300">引擎空闲，等待下一次计划任务</div>
            </div>
          )}

          <div className="mt-3.5">
            <div className="text-[11px] text-gray-500 font-semibold mb-1.5">
              即将运行 · 未来 12 小时
            </div>
            {status.upcoming.length ? (
              <div>
                {status.upcoming.map((item) => (
                  <div
                    key={`${item.taskName}-${item.runAt}`}
                    className="flex items-center gap-2.5 text-xs py-1.5 border-b border-dashed border-gray-800 last:border-b-0"
                  >
                    <span className="w-10 shrink-0 font-mono text-gray-400">
                      {dayjs(item.runAt).format('HH:mm')}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-gray-100">{item.taskLabel}</span>
                    {item.source && <Tag className="!mr-0">{item.source}</Tag>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-500 py-2">暂无计划任务</div>
            )}
          </div>

          <div className="mt-3.5">
            <div className="text-[11px] text-gray-500 font-semibold mb-1.5">最近运行</div>
            {status.recentRuns.length ? (
              <div>
                {status.recentRuns.map((run, i) => (
                  <div
                    key={`${run.taskName}-${run.startedAt ?? i}`}
                    className="flex items-center gap-2.5 text-xs py-1.5 border-b border-dashed border-gray-800 last:border-b-0"
                  >
                    <span className={`w-1.5 h-1.5 shrink-0 rounded-full ${runDotClass(run.status)}`} />
                    <span className="min-w-0 flex-1 truncate text-gray-100">{run.taskLabel}</span>
                    <span className="shrink-0 font-mono text-[11px] text-gray-500">
                      {run.finishedAt ? dayjs(run.finishedAt).format('HH:mm') : '--:--'}
                      {run.durationSeconds != null && ` · ${formatDuration(run.durationSeconds)}`}
                      {run.recordsCount != null && ` · ${run.recordsCount} 条`}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-gray-500 py-2">暂无运行记录</div>
            )}
          </div>

          <div className="flex-1" />
          <div className="pt-2.5 text-[10px] text-gray-600 border-t border-dashed border-gray-800">
            采集计划由调度器自动执行，详情与手动触发在「任务管理」
          </div>
        </div>
      )}
    </FoldCard>
  )
}
