import { Spin } from 'antd'
import axios from 'axios'

import type { IndexKlinePeriod, MovingAverageConfig } from '@ai-invest/shared'
import { IndexKlineChart } from '@/components/charts/IndexKlineChart'
import { useIndexKline } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'

interface IndexKlinePanelProps {
  code: string
  period: IndexKlinePeriod
  maConfigs: MovingAverageConfig[]
}

const PERIOD_LABEL: Record<IndexKlinePeriod, string> = {
  daily: '日线',
  weekly: '周线',
  monthly: '月线',
  quarterly: '季线',
  yearly: '年线',
}

export function IndexKlinePanel({ code, period, maConfigs }: IndexKlinePanelProps) {
  useColorScheme()
  const { data, isLoading, error } = useIndexKline(code, period)

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spin />
      </div>
    )
  }

  if (error || !data) {
    const detail = axios.isAxiosError(error)
      ? (error.response?.data as { detail?: string } | undefined)?.detail
      : null
    return (
      <div className="text-gray-500 text-sm py-8 text-center">
        {detail ?? '暂无 K 线数据'}
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
      <div className="flex items-baseline gap-3 mb-2">
        <span className="text-2xl font-semibold font-mono" style={{ color: changeHex(changePct) }}>
          {last?.close != null ? last.close.toFixed(2) : '-'}
        </span>
        <span className="text-sm font-mono" style={{ color: changeHex(changePct) }}>
          {changePct != null ? formatPercent(changePct) : '-'}
        </span>
        <span className="text-xs text-gray-500 ml-auto">
          {PERIOD_LABEL[period]} · {last?.date ?? '-'}
        </span>
      </div>
      {data.bars.length > 0 ? (
        <IndexKlineChart
          bars={data.bars}
          maConfigs={maConfigs}
          height={340}
          defaultVisibleBars={period === 'daily' ? 120 : undefined}
        />
      ) : (
        <div className="text-gray-500 text-sm py-8 text-center">
          暂无 K 线数据（指数日 K 采集任务运行后可用）
        </div>
      )}
    </div>
  )
}
