import { FileTextOutlined, HeartOutlined, HeartTwoTone, WalletOutlined } from '@ant-design/icons'
import { Button, Card, Empty, List, Space, Spin, Statistic, Tabs, Tag, Typography } from 'antd'
import { useParams } from 'react-router-dom'

import { KlineChart } from '@/components/charts/KlineChart'
import { useResearch } from '@/hooks/useResearch'
import { useKline, useStockDetail } from '@/hooks/useStocks'
import { useFinancial } from '@/hooks/useFinancial'
import { useAddWatchlistItem, useWatchlist } from '@/hooks/useWatchlist'
import type { ResearchReport } from '@ai-invest/shared'

const METRIC_LABELS: Record<string, string> = {
  debt_ratio: '资产负债率',
  current_ratio: '流动比率',
  roe: '净资产收益率 (ROE)',
  gross_margin: '毛利率',
  net_margin: '净利率',
  operating_cf_ratio: '经营现金流/营收',
}

function StockFinancial({ code }: { code: string }) {
  const { data, isLoading } = useFinancial(code)

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spin size="large" />
      </div>
    )
  }

  if (!data) {
    return <Empty description="暂无财务数据" />
  }

  const renderPercent = (value: number | null) =>
    value === null ? '-' : `${(value * 100).toFixed(2)}%`

  return (
    <div className="space-y-4">
      <Space>
        <Tag>报告期：{data.reportDate || '-'}</Tag>
        <Tag>类型：{data.reportType || '-'}</Tag>
      </Space>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(data.metrics).map(([key, value]) => (
          <Card key={key} variant="borderless">
            <Statistic title={METRIC_LABELS[key] || key} value={renderPercent(value)} />
          </Card>
        ))}
      </div>
    </div>
  )
}

function StockResearch({ code }: { code: string }) {
  const { data, isLoading } = useResearch({ stockCode: code, pageSize: 5 })

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spin size="large" />
      </div>
    )
  }

  if (!data?.items.length) {
    return <Empty description="暂无相关研报" />
  }

  return (
    <List
      dataSource={data.items}
      renderItem={(item: ResearchReport) => (
        <List.Item>
          <List.Item.Meta
            title={
              <Space>
                <FileTextOutlined />
                <span>{item.title}</span>
              </Space>
            }
            description={
              <Space direction="vertical" size={0}>
                <Typography.Text type="secondary">
                  {item.source || '未知来源'} · {item.publishDate || '-'}
                </Typography.Text>
                {item.summary && <Typography.Paragraph>{item.summary}</Typography.Paragraph>}
              </Space>
            }
          />
        </List.Item>
      )}
    />
  )
}

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
      label: (
        <Space>
          <WalletOutlined />
          财务体检
        </Space>
      ),
      children: (
        <Card variant="borderless">
          <StockFinancial code={stockCode} />
        </Card>
      ),
    },
    {
      key: 'research',
      label: (
        <Space>
          <FileTextOutlined />
          研报观点
        </Space>
      ),
      children: (
        <Card variant="borderless">
          <StockResearch code={stockCode} />
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
