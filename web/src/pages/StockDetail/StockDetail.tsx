import { HeartOutlined, HeartTwoTone } from '@ant-design/icons'
import { Button, Card, Space, Spin, Tabs, Tag, Typography } from 'antd'
import { useParams } from 'react-router-dom'

import { KlineChart } from '@/components/charts/KlineChart'
import { useKline, useStockDetail } from '@/hooks/useStocks'
import { useAddWatchlistItem, useWatchlist } from '@/hooks/useWatchlist'

export function StockDetail() {
  const { code } = useParams<{ code?: string }>()
  const stockCode = code || ''

  const { data: stock, isLoading: stockLoading } = useStockDetail(stockCode)
  const { data: klineData, isLoading: klineLoading } = useKline(stockCode, 200)
  const { data: watchlist } = useWatchlist()
  const addMutation = useAddWatchlistItem()

  const isWatched = watchlist?.some((item) => item.code === stockCode)

  const handleToggleWatchlist = () => {
    if (!isWatched) {
      addMutation.mutate({ stockCode, tags: [] })
    }
  }

  if (stockLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spin size="large" />
      </div>
    )
  }

  if (!stock) {
    return <Typography.Text type="danger">未找到股票 {stockCode}</Typography.Text>
  }

  const tabItems = [
    {
      key: 'kline',
      label: 'K线分析',
      children: (
        <Card variant="borderless">
          {klineLoading ? (
            <div className="flex justify-center py-20"><Spin size="large" /></div>
          ) : klineData?.items.length ? (
            <KlineChart data={klineData.items} height={500} />
          ) : (
            <Typography.Text type="secondary">暂无 K 线数据</Typography.Text>
          )}
        </Card>
      ),
    },
    {
      key: 'financial',
      label: '财务体检',
      children: (
        <Card variant="borderless">
          <Typography.Text type="secondary">财务体检功能开发中，敬请期待。</Typography.Text>
        </Card>
      ),
    },
    {
      key: 'research',
      label: '研报观点',
      children: (
        <Card variant="borderless">
          <Typography.Text type="secondary">研报观点功能开发中，敬请期待。</Typography.Text>
        </Card>
      ),
    },
    {
      key: 'news',
      label: '相关新闻',
      children: (
        <Card variant="borderless">
          <Typography.Text type="secondary">相关新闻功能开发中，敬请期待。</Typography.Text>
        </Card>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Typography.Title level={3} className="!mb-1">
            {stock.name} <span className="text-lg text-gray-400">{stock.code}</span>
          </Typography.Title>
          <Space size="middle">
            <Tag color="blue">{stock.market}</Tag>
            {stock.industry && <Tag>{stock.industry}</Tag>}
          </Space>
        </div>
        <Button
          type={isWatched ? 'default' : 'primary'}
          icon={isWatched ? <HeartTwoTone twoToneColor="#eb2f96" /> : <HeartOutlined />}
          onClick={handleToggleWatchlist}
          loading={addMutation.isPending}
          disabled={isWatched}
        >
          {isWatched ? '已加入自选' : '加入自选'}
        </Button>
      </div>

      <Tabs defaultActiveKey="kline" items={tabItems} />
    </div>
  )
}
