import { Empty, Spin } from 'antd'

import { useMarketStats } from '@/hooks/useMarket'
import { changeHex } from '@/utils/formatters'

/** 市场情绪指数：0-100 温度计（50 为中性基准），渐变 meter 恐惧 → 贪婪。 */
export function SentimentCard() {
  const { data, isLoading } = useMarketStats()

  if (isLoading) {
    return <div className="flex justify-center py-12"><Spin /></div>
  }
  if (data?.emotionScore == null) {
    return <Empty description="暂无情绪数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  const score = data.emotionScore
  // 高于 50 视为"偏热"，按涨跌语义着色（国内习惯红涨绿跌，随配色方案切换）
  const color = changeHex(score - 50)
  const context =
    data.upCount != null && data.downCount != null
      ? `${data.tradeDate} · 涨${data.upCount}家 / 跌${data.downCount}家`
      : data.tradeDate
  return (
    <div>
      <div className="flex items-center gap-4">
        <div className="text-[2rem] font-bold leading-none" style={{ color }}>
          {Math.round(score)}
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-medium" style={{ color }}>
            {data.emotionLabel ?? '-'}
          </div>
          <div className="truncate text-[11px] text-gray-500">{context}</div>
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-800">
        <div
          className="h-full rounded-full"
          style={{
            width: `${score}%`,
            background: 'linear-gradient(90deg, #2ea043, #d29922, #f85149)',
          }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-gray-600">
        <span>恐惧</span>
        <span>中性</span>
        <span>贪婪</span>
      </div>
    </div>
  )
}
