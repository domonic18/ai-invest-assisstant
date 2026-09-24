import { Card, Empty, Space, Spin, Typography } from 'antd'

import { PaperTradeOrderHistory } from './PaperTradeOrderHistory'
import { PaperTradeOverview } from './PaperTradeOverview'
import { PaperTradePositions } from './PaperTradePositions'
import { NavChart } from './NavChart'
import { usePaperTradeNav, usePaperTradeOverview } from '@/hooks/usePaperTrade'
import { bjNow } from '@/utils/beijing'
import { DATE_FORMAT } from '@/utils/formatters'

/** 未配置引导卡：enabled=false（服务端未配 PAPER_TRADE_URL 或柜台凭据无效）。 */
function GuideCard() {
  return (
    <Card size="small">
      <Empty description="模拟盘功能未启用">
        <Space direction="vertical" size={4}>
          <Typography.Text type="secondary">
            需要在服务端配置 GMTRADE_TOKEN / GMTRADE_ACCOUNT_ID 并启动 paper-trade 服务
          </Typography.Text>
          <Typography.Text type="secondary">
            token 在 sim.myquant.cn 个人中心获取，视同密码保管
          </Typography.Text>
        </Space>
      </Empty>
    </Card>
  )
}

/** 模拟盘页：资金总览 / 持仓 / 净值曲线 / 委托成交历史（只读，批次 2）。 */
export function PaperTrade() {
  const overviewQuery = usePaperTradeOverview()
  const navQuery = usePaperTradeNav(30)

  if (overviewQuery.isLoading) {
    return (
      <div className="p-4 flex justify-center py-24">
        <Spin />
      </div>
    )
  }

  const overview = overviewQuery.data
  if (!overview?.enabled) {
    return (
      <div className="p-4">
        <GuideCard />
      </div>
    )
  }

  // 当日盈亏 = 实时 nav - 最近一个「今日之前」的快照 nav - 当日出入金
  const todayStr = bjNow().format(DATE_FORMAT)
  const prevPoint = [...(navQuery.data?.items ?? [])]
    .reverse()
    .find((p) => p.tradeDate < todayStr)
  const dayPnl =
    overview.cash?.nav != null && prevPoint?.nav != null
      ? overview.cash.nav - prevPoint.nav - (overview.cash.lastInout ?? 0)
      : null

  return (
    <div className="p-4 space-y-4">
      <PaperTradeOverview cash={overview.cash} dayPnl={dayPnl} />
      <PaperTradePositions positions={overview.positions} loading={overviewQuery.isFetching} />
      <NavChart items={navQuery.data?.items ?? []} loading={navQuery.isLoading} />
      <Card size="small" title="委托与成交">
        <PaperTradeOrderHistory />
      </Card>
    </div>
  )
}
