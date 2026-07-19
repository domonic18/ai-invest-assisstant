import { Segmented } from 'antd'
import { useState } from 'react'

import type { IndexKlinePeriod } from '@ai-invest/shared'

import { IndexIntradayPanel } from './IndexIntradayPanel'
import { IndexKlinePanel } from './IndexKlinePanel'
import { useMaConfigs } from '@/stores/settings'

interface IndexChartPanelProps {
  code: string
  tradeDate?: string
}

type PeriodKey = 'intraday' | IndexKlinePeriod

const PERIOD_OPTIONS: { value: PeriodKey; label: string }[] = [
  { value: 'intraday', label: '分时' },
  { value: 'daily', label: '日线' },
  { value: 'weekly', label: '周线' },
  { value: 'monthly', label: '月线' },
  { value: 'quarterly', label: '季线' },
  { value: 'yearly', label: '年线' },
]

export function IndexChartPanel({ code, tradeDate }: IndexChartPanelProps) {
  const [period, setPeriod] = useState<PeriodKey>('intraday')
  const maConfigs = useMaConfigs()

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-3">
        <Segmented
          size="small"
          options={PERIOD_OPTIONS}
          value={period}
          onChange={(value) => setPeriod(value as PeriodKey)}
        />
      </div>
      {period === 'intraday' ? (
        <IndexIntradayPanel code={code} tradeDate={tradeDate} />
      ) : (
        <IndexKlinePanel code={code} period={period} maConfigs={maConfigs} />
      )}
    </div>
  )
}
