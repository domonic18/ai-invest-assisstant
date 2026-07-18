import { Spin } from 'antd'
import axios from 'axios'

import { IntradayChart } from '@/components/charts/IntradayChart'
import { useIndexIntraday } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'

interface IndexIntradayPanelProps {
  code: string
  tradeDate?: string
}

export function IndexIntradayPanel({ code, tradeDate }: IndexIntradayPanelProps) {
  useColorScheme()
  const { data, isLoading, error } = useIndexIntraday(code, tradeDate)

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
        {detail ?? '暂无分时数据'}
      </div>
    )
  }

  const last = data.points[data.points.length - 1]
  const changePct = last ? ((last.price - data.prevClose) / data.prevClose) * 100 : null

  return (
    <div>
      <div className="flex items-baseline gap-3 mb-2">
        <span className="text-2xl font-semibold font-mono" style={{ color: changeHex(changePct) }}>
          {last ? last.price.toFixed(2) : '-'}
        </span>
        <span className="text-sm font-mono" style={{ color: changeHex(changePct) }}>
          {changePct != null ? formatPercent(changePct) : '-'}
        </span>
        <span className="text-xs text-gray-500 ml-auto">
          分时 · {data.tradeDate}
        </span>
      </div>
      {data.points.length > 0 ? (
        <IntradayChart data={data} height={340} />
      ) : (
        <div className="text-gray-500 text-sm py-8 text-center">暂无分时数据</div>
      )}
    </div>
  )
}
