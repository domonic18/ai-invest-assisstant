import { Card, Empty, List, Spin } from 'antd'
import { Link } from 'react-router-dom'

import type { WatchlistQuote } from '@ai-invest/shared'
import { useWatchlistQuotes } from '@/hooks/useMarket'
import { SourceNote } from '@/components/common/SourceNote'
import { IntradaySpark } from '@/components/charts/IntradaySpark'
import { useColorScheme } from '@/stores/settings'
import { changeColor, formatPercent } from '@/utils/formatters'

interface WatchlistQuotesCardProps {
  /** 传入时直接使用（工作台聚合数据），缺省自取（每日复盘页行为不变）。 */
  quotes?: WatchlistQuote[]
  loading?: boolean
}

export function WatchlistQuotesCard({ quotes, loading }: WatchlistQuotesCardProps) {
  useColorScheme()
  const self = useWatchlistQuotes()
  const data = quotes ?? self.data
  const isLoading = loading ?? self.isLoading

  return (
    <Card
      variant="borderless"
      title="自选股行情"
      extra={<Link to="/watchlist" className="text-xs">管理自选</Link>}
    >
      {isLoading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : data?.length ? (
        <List
          dataSource={data}
          renderItem={(item) => (
            <List.Item className="!px-0">
              <div className="flex items-center justify-between w-full gap-2">
                <div className="min-w-0">
                  <Link to={`/stock/${item.code}`} className="font-medium">
                    {item.name ?? item.code}
                  </Link>
                  <span className="ml-2 text-xs text-gray-500 font-mono">{item.code}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <IntradaySpark points={item.trend} changePct={item.changePct} width={64} />
                  <div className="text-right">
                    <div className="font-mono text-sm">
                      {item.price != null ? item.price.toFixed(2) : '-'}
                    </div>
                    <div className={`text-xs ${changeColor(item.changePct)}`}>
                      {item.changePct != null ? formatPercent(item.changePct) : '-'}
                    </div>
                  </div>
                </div>
              </div>
            </List.Item>
          )}
        />
      ) : (
        <Empty description="暂无自选股" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      <SourceNote>新浪财经实时行情快照</SourceNote>
    </Card>
  )
}
