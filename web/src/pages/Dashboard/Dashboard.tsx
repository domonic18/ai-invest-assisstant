import { ArrowRightOutlined, PlusOutlined, RiseOutlined } from '@ant-design/icons'
import { Button, Card, Empty, List, Space, Spin, Statistic, Table, Typography } from 'antd'
import { Link } from 'react-router-dom'

import { LineMiniChart } from '@/components/charts/LineMiniChart'
import { StockSearch } from '@/components/common/StockSearch'
import { useFundFlow } from '@/hooks/useFundFlow'
import { useWatchlist } from '@/hooks/useWatchlist'
import { formatNumber, formatPercent } from '@/utils/formatters'

export function Dashboard() {
  const { data: watchlist, isLoading: watchlistLoading } = useWatchlist()
  const { data: fundFlow, isLoading: fundFlowLoading } = useFundFlow(undefined, 5)

  const fundFlowColumns = [
    { title: '股票代码', dataIndex: 'code', key: 'code' },
    { title: '日期', dataIndex: 'date', key: 'date' },
    {
      title: '主力净流入',
      dataIndex: 'mainNetInflow',
      key: 'mainNetInflow',
      render: (value: number) => (
        <span className={value >= 0 ? 'text-green-500' : 'text-red-500'}>
          {formatNumber(value / 10000, 2)} 万
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Typography.Title level={4} className="!mb-0">每日复盘</Typography.Title>
        <StockSearch onSelect={(code) => window.location.assign(`/stock/${code}`)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { title: '上证指数', value: 3052.37, change: 0.42 },
          { title: '深证成指', value: 9750.81, change: -0.18 },
          { title: '创业板指', value: 1903.86, change: 0.31 },
          { title: '科创50', value: 820.46, change: -0.25 },
        ].map((item) => (
          <Card key={item.title} variant="borderless" bodyStyle={{ padding: 16 }}>
            <Statistic
              title={item.title}
              value={item.value}
              precision={2}
              valueStyle={{ color: item.change >= 0 ? '#2ea043' : '#f85149' }}
              suffix={formatPercent(item.change)}
            />
            <LineMiniChart
              data={[item.value * 0.98, item.value * 0.99, item.value, item.value * 1.01, item.value]}
              color={item.change >= 0 ? '#2ea043' : '#f85149'}
              height={80}
            />
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card
          title="我的自选股"
          variant="borderless"
          className="lg:col-span-1"
          extra={
            <Link to="/settings">管理自选</Link>
          }
        >
          {watchlistLoading ? (
            <div className="flex justify-center py-8"><Spin /></div>
          ) : watchlist?.length ? (
            <List
              dataSource={watchlist}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Link key="detail" to={`/stock/${item.code}`}>详情</Link>,
                  ]}
                >
                  <List.Item.Meta
                    title={<Link to={`/stock/${item.code}`}>{item.code}</Link>}
                    description={item.tags?.join(', ') || '暂无标签'}
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无自选股" />
          )}
        </Card>

        <Card
          title="资金流向摘要"
          variant="borderless"
          className="lg:col-span-2"
          extra={<Link to="/capital-flow">更多 <ArrowRightOutlined /></Link>}
        >
          {fundFlowLoading ? (
            <div className="flex justify-center py-8"><Spin /></div>
          ) : (
            <Table
              dataSource={fundFlow?.items || []}
              columns={fundFlowColumns}
              rowKey={(record) => `${record.code}-${record.date}`}
              pagination={false}
              size="small"
            />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="产业链分析" variant="borderless">
          <Space direction="vertical" className="w-full">
            <Typography.Text type="secondary">选择行业，生成 AI 产业链图谱与投资策略。</Typography.Text>
            <Link to="/chain/半导体">
              <Button type="primary" icon={<RiseOutlined />}>分析半导体产业链</Button>
            </Link>
          </Space>
        </Card>

        <Card title="快速入口" variant="borderless">
          <Space wrap>
            <Link to="/auction"><Button icon={<PlusOutlined />}>集合竞价复盘</Button></Link>
            <Link to="/hotspot"><Button>热点追踪</Button></Link>
            <Link to="/research"><Button>研报中心</Button></Link>
          </Space>
        </Card>
      </div>
    </div>
  )
}
