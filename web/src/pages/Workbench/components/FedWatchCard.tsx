import { Empty, Spin } from 'antd'
import dayjs from 'dayjs'
import type { ReactNode } from 'react'

import type { FedWatchMeeting } from '@ai-invest/shared'

import { useFedWatch } from '@/hooks/useMarket'

import { FoldCard } from './FoldCard'

const CUT_COLOR = '#5e6ad2'
const HOLD_COLOR = '#58a6ff'
const HIKE_COLOR = '#8a8f98'

/** 目标区间 bps → 百分比区间文案（375-400 → 3.75-4.00%）。 */
function rangeLabel(low: number, high: number): string {
  return `${(low / 100).toFixed(2)}-${(high / 100).toFixed(2)}%`
}

function ProbRow({ label, prob, color }: { label: string; prob: number; color: string }) {
  return (
    <div className="flex items-center gap-2.5 text-xs">
      <span className="w-[76px] shrink-0 text-gray-400">{label}</span>
      <div className="flex-1 h-3 rounded-md bg-[#181a21] overflow-hidden">
        <div
          className="h-full rounded-md"
          style={{ width: `${Math.min(prob, 100)}%`, background: color }}
        />
      </div>
      <span className="w-11 text-right font-mono font-semibold text-gray-200">
        {prob.toFixed(1)}%
      </span>
    </div>
  )
}

interface FedWatchCardProps {
  className?: string
  stretch?: boolean
}

/** 加息概率卡（CME FedWatch，每日 07:30 采集），与工作台各版块同构的 FoldCard。 */
export function FedWatchCard({ className, stretch }: FedWatchCardProps) {
  const { data, isLoading } = useFedWatch()

  let body: ReactNode
  if (isLoading) {
    body = (
      <div className="flex justify-center py-6">
        <Spin />
      </div>
    )
  } else if (!data || data.meetings.length === 0) {
    body = (
      <Empty
        className="py-6"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="暂无 FedWatch 数据（每日 07:30 采集后可用）"
      />
    )
  } else {
    const next: FedWatchMeeting = data.meetings[0]
    const meetingDay = dayjs(next.meetingDate)
    const daysToMeet = meetingDay.startOf('day').diff(dayjs().startOf('day'), 'day')
    body = (
      <div className="flex flex-1 flex-col justify-center gap-3">
        <div className="text-[13px] text-gray-300">
          {meetingDay.format('M 月 D 日')}议息
          {daysToMeet > 0 ? ` · T-${daysToMeet}天` : ''}
        </div>
        <div className="flex flex-col gap-2">
          <ProbRow label="降息（累计）" prob={next.probCut} color={CUT_COLOR} />
          <ProbRow label="维持不变" prob={next.probHold} color={HOLD_COLOR} />
          <ProbRow label="加息（累计）" prob={next.probHike} color={HIKE_COLOR} />
        </div>
        <div className="mt-auto pt-2.5 text-[10px] text-gray-600 border-t border-dashed border-gray-800">
          CME FedWatch · 截至 {dayjs(data.dataAsAt).format('MM-DD HH:mm')} CT · 最可能区间{' '}
          {rangeLabel(next.likelyRangeLow, next.likelyRangeHigh)}
        </div>
      </div>
    )
  }

  return (
    <FoldCard title="加息概率" className={className} stretch={stretch}>
      {body}
    </FoldCard>
  )
}
