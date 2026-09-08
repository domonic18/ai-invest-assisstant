import { Card, Empty, Spin } from 'antd'

import { SourceNote } from '@/components/common/SourceNote'
import { useSectorQuotes } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'

/** 热力 chip 数（原型 Card0：|涨跌幅| top16）。 */
const TOP_N = 16

export function SectorQuoteHeatCard() {
  useColorScheme()
  const { data, isLoading } = useSectorQuotes('industry')

  const chips = (data?.items ?? [])
    .filter((item) => item.changePct !== null)
    .sort((a, b) => Math.abs(b.changePct ?? 0) - Math.abs(a.changePct ?? 0))
    .slice(0, TOP_N)

  return (
    <Card
      variant="borderless"
      title={`板块指数表现${data?.tradeDate ? `（${data.tradeDate}）` : ''}`}
    >
      {isLoading ? (
        <div className="flex justify-center py-10">
          <Spin />
        </div>
      ) : chips.length === 0 ? (
        <Empty
          className="py-10"
          description="暂无板块行情快照（采集任务交易日 16:05 运行后可用）"
        />
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {chips.map((item) => {
              const hex = changeHex(item.changePct)
              return (
                <span
                  key={`${item.sectorType}-${item.sectorCode}`}
                  title={`领涨：${item.leaderStockName ?? '-'} · 涨${item.upCount ?? '-'}家 / 跌${item.downCount ?? '-'}家 · 换手 ${item.turnoverRate === null ? '-' : item.turnoverRate.toFixed(2) + '%'}`}
                  className="px-2.5 py-1 rounded-md text-xs font-medium cursor-default transition-transform hover:scale-105"
                  style={{ background: `${hex}1f`, color: hex }}
                >
                  {item.sectorName} {formatPercent(item.changePct ?? 0)}
                </span>
              )
            })}
          </div>
          <SourceNote>
            东方财富行业板块日快照（按当日涨跌幅绝对值取前 {TOP_N}），每日收盘后采集
          </SourceNote>
        </>
      )}
    </Card>
  )
}
