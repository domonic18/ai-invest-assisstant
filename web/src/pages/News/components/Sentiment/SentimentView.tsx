/** 大 V 情绪 Tab 容器：时间范围为账号卡与情绪流共享状态（账号卡计数/时序随之变化）。 */

import { useState } from 'react'

import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { useSocialAccountCards } from '@/hooks/useSocialSentiment'

import { AccountDimension } from './AccountDimension'
import { SentimentStream } from './SentimentStream'

export function SentimentView() {
  const [selected, setSelected] = useState<ApiSocialAccountCard | null>(null)
  // 与情绪流一致默认 7 天；undefined = 不限时间（全部历史）
  const [hours, setHours] = useState<number | undefined>(168)
  const { data, isLoading } = useSocialAccountCards(hours)

  return (
    <div className="space-y-3">
      <AccountDimension
        accounts={data?.accounts ?? []}
        isLoading={isLoading}
        selectedId={selected?.id ?? null}
        onSelect={setSelected}
      />
      <SentimentStream
        hours={hours}
        onHoursChange={setHours}
        account={selected}
        onClearAccount={() => setSelected(null)}
      />
    </div>
  )
}
