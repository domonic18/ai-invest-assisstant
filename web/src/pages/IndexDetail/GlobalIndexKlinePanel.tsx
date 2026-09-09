import { Segmented, Spin } from 'antd'
import { useState } from 'react'

import type { IndexKlinePeriod, MovingAverageConfig } from '@ai-invest/shared'
import { IndexKlineChart } from '@/components/charts/IndexKlineChart'
import { useGlobalIndexKline } from '@/hooks/useMarket'
import { useColorScheme, useMaConfigs } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'
import { apiErrorMessage } from '@/utils/errorMessage'

interface GlobalIndexKlinePanelProps {
  code: string
  /** 债券收益率类指标保留 3 位小数。 */
  decimals?: number
}

type PeriodKey = IndexKlinePeriod

const PERIOD_OPTIONS: { value: PeriodKey; label: string }[] = [
  { value: 'daily', label: '日线' },
  { value: 'weekly', label: '周线' },
  { value: 'monthly', label: '月线' },
  { value: 'quarterly', label: '季线' },
  { value: 'yearly', label: '年线' },
]

const PERIOD_LABEL: Record<PeriodKey, string> = {
  daily: '日线',
  weekly: '周线',
  monthly: '月线',
  quarterly: '季线',
  yearly: '年线',
}

/** 全球指标详情 K 线面板：股指/商品/汇率为蜡烛图，债券收益率/利差为收盘线（源无 OHLC）。 */
export function GlobalIndexKlinePanel({ code, decimals = 2 }: GlobalIndexKlinePanelProps) {
  useColorScheme()
  const [period, setPeriod] = useState<PeriodKey>('daily')
  const maConfigs: MovingAverageConfig[] = useMaConfigs()
  const { data, isLoading, error } = useGlobalIndexKline(code, period)

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spin />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-gray-500 text-sm py-8 text-center">
        {apiErrorMessage(error, '暂无 K 线数据')}
      </div>
    )
  }

  const last = data.bars[data.bars.length - 1]
  const prev = data.bars[data.bars.length - 2]
  const changePct =
    last?.close != null && prev?.close
      ? ((last.close - prev.close) / prev.close) * 100
      : null

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
      <div className="flex items-baseline gap-3 mb-2">
        <span className="text-2xl font-semibold font-mono" style={{ color: changeHex(changePct) }}>
          {last?.close != null ? last.close.toFixed(decimals) : '-'}
        </span>
        <span className="text-sm font-mono" style={{ color: changeHex(changePct) }}>
          {changePct != null ? formatPercent(changePct) : '-'}
        </span>
        <span className="text-xs text-gray-500 ml-auto">
          {PERIOD_LABEL[period]} · {last?.date ?? '-'}
        </span>
      </div>
      {data.bars.length > 1 ? (
        <IndexKlineChart
          bars={data.bars}
          maConfigs={maConfigs}
          height={340}
          defaultVisibleBars={period === 'daily' ? 120 : undefined}
        />
      ) : (
        <div className="text-gray-500 text-sm py-8 text-center">
          历史数据积累中（当前 {data.bars.length} 个交易日，采集任务每日自动补充）
        </div>
      )}
    </div>
  )
}
