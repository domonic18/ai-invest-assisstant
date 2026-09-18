/** 日历 chip：按业务分类着色，hover 显示任务/cron 信息，点击开详情。 */

import { Tooltip } from 'antd'

import { taskCategoryColor } from '@/utils/taskCategoryMeta'

import { withAlpha, type CalEntry } from './calendarUtils'

interface CalChipProps {
  entry: CalEntry
  onOpen: (taskKey: string) => void
}

function chipText(entry: CalEntry): string {
  if (entry.band) {
    const step = entry.task.parsed.minuteStep ?? 1
    return `${entry.task.label} ${step === 1 ? '每分钟' : `每 ${step} 分钟`}`
  }
  return `${String(entry.min).padStart(2, '0')} ${entry.task.label}`
}

export function CalChip({ entry, onOpen }: CalChipProps) {
  const { task } = entry
  const color = taskCategoryColor(task.category)
  const tip = (
    <div className="text-xs">
      <div className="font-medium">{task.label}</div>
      <div className="font-mono opacity-70">{task.schedule}</div>
      {task.zh && <div className="opacity-80">{task.zh}</div>}
    </div>
  )
  return (
    <Tooltip title={tip}>
      <button
        type="button"
        onClick={() => onOpen(task.key)}
        className="max-w-full cursor-pointer truncate rounded px-1.5 py-0.5 text-left text-[11px] leading-4 transition-opacity hover:opacity-80"
        style={{ background: withAlpha(color, 0.16), color }}
      >
        {chipText(entry)}
      </button>
    </Tooltip>
  )
}
