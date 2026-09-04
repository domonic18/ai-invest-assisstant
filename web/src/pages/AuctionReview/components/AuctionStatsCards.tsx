import { Card } from 'antd'

import { countFeature, type AuctionDayStat } from '../utils'

interface AuctionStatsCardsProps {
  stats: AuctionDayStat[]
}

/** 汇总卡（原型 5 张中数据可支撑的 3 张）：交易日数 / 放量日 / 缩量日。 */
export function AuctionStatsCards({ stats }: AuctionStatsCardsProps) {
  const cards = [
    { label: '交易日数', value: String(stats.length), sub: '查询区间内有竞价数据' },
    { label: '放量日', value: String(countFeature(stats, 'high')), sub: '量比 ≥ 1.2' },
    { label: '缩量日', value: String(countFeature(stats, 'low')), sub: '量比 ≤ 0.8' },
  ]
  return (
    <div className="grid grid-cols-3 gap-4">
      {cards.map((card) => (
        <Card key={card.label} variant="borderless" size="small">
          <div className="text-[11px] text-gray-400">{card.label}</div>
          <div className="text-[22px] font-bold font-mono mt-0.5">{card.value}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">{card.sub}</div>
        </Card>
      ))}
    </div>
  )
}
