/** 大 V 情绪 Tab 容器：账号维度卡 + 情绪流（点击账号卡切换时间线）。 */

import { useState } from 'react'

import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { AccountDimension } from './AccountDimension'
import { SentimentStream } from './SentimentStream'

export function SentimentView() {
  const [selected, setSelected] = useState<ApiSocialAccountCard | null>(null)

  return (
    <div className="space-y-3">
      <AccountDimension selectedId={selected?.id ?? null} onSelect={setSelected} />
      <SentimentStream
        account={selected}
        onClearAccount={() => setSelected(null)}
      />
    </div>
  )
}
