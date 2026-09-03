import { Skeleton } from 'antd'

import type { GlobalIndexQuote } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'

interface GlobalIndicesRowProps {
  indices?: GlobalIndexQuote[]
  loading?: boolean
}

export function GlobalIndicesRow({ indices, loading }: GlobalIndicesRowProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 1 }} />
  }
  if (!indices?.length) {
    return <div className="text-gray-500 text-sm py-3 text-center">暂无全球指标数据</div>
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {indices.map((item) => (
        <div key={item.indexCode} className="rounded bg-[#1a1d24] p-3">
          <div className="text-xs text-gray-400">{item.indexName}</div>
          <div
            className="text-lg font-semibold font-mono"
            style={{ color: changeHex(item.changePct) }}
          >
            {item.close != null
              ? item.close.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
              : '-'}
          </div>
          <div className="text-xs" style={{ color: changeHex(item.changePct) }}>
            {item.changePct != null ? formatPercent(item.changePct) : '-'}
          </div>
        </div>
      ))}
    </div>
  )
}
