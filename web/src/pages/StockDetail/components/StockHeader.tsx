import { HeartOutlined, HeartTwoTone } from '@ant-design/icons'
import { Button, Skeleton, Tag, Typography } from 'antd'

interface StockHeaderProps {
  stock?: {
    name: string
    code: string
    market: string
    industry?: string | null
  } | null
  stockCode: string
  isWatched?: boolean
  onToggleWatchlist: () => void
  isWatchlistLoading?: boolean
}

export function StockHeader({
  stock,
  stockCode,
  isWatched,
  onToggleWatchlist,
  isWatchlistLoading,
}: StockHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        {stock ? (
          <>
            <Typography.Title level={5} className="!mb-0 text-[#d1d4dc]">
              {stock.name}
            </Typography.Title>
            <span className="text-sm text-[#8c8c8c]">{stockCode}</span>
            <Tag color="blue" className="!text-xs">{stock.market}</Tag>
            {stock.industry && <Tag className="!text-xs">{stock.industry}</Tag>}
          </>
        ) : (
          <>
            <Skeleton.Input active size="small" style={{ width: 120 }} />
            <span className="text-sm text-[#8c8c8c]">{stockCode}</span>
          </>
        )}
      </div>
      <Button
        type={isWatched ? 'default' : 'primary'}
        size="small"
        icon={isWatched ? <HeartTwoTone twoToneColor="#eb2f96" /> : <HeartOutlined />}
        onClick={onToggleWatchlist}
        loading={isWatchlistLoading}
        disabled={isWatched || !stock}
      >
        {isWatched ? '已加入自选' : '加入自选'}
      </Button>
    </div>
  )
}
