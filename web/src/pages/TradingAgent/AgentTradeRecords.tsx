/**
 * Agent 持仓与交易（模拟管理页 tab，D29 重构）：agent 专属账户的资金
 * 五指标（总资产/持仓市值/可用资金/累计盈亏/当日盈亏）+ 当前持仓 +
 * 委托/成交记录（日期选择即历史查询）。
 *
 * 账户 id 从 admin 账户列表取 agentKey 绑定行；持仓表复用模拟盘页导出的
 * PaperTradePositions（不传 onTrade，agent 账户人工不在此直接下单）；
 * 累计盈亏 = nav − cumInout，当日盈亏 = 实时 nav − 最近快照 nav（前端算，
 * 缺快照显示 -）。
 */
import { Card, Empty, Space, Spin, Statistic, Tabs } from 'antd'

import { PaperTradeExecutionsPanel, PaperTradeOrdersPanel } from '@/pages/PaperTrade/PaperTradeOrderHistory'
import { PaperTradePositions } from '@/pages/PaperTrade/PaperTradePositions'
import {
  useAdminPaperTradeAccounts,
  usePaperTradeNav,
  usePaperTradeOverview,
} from '@/hooks/usePaperTrade'
import { changeColor, formatAmount } from '@/utils/formatters'

import { useAgentKey } from './agentKeyContext'

function PnlStatistic({ title, pnl }: { title: string; pnl: number | null }) {
  return (
    <Statistic
      title={title}
      value={pnl == null ? '-' : `${pnl >= 0 ? '+' : ''}${formatAmount(pnl)}`}
      valueStyle={{ fontSize: 18, ...(pnl != null ? { color: changeColor(pnl) } : {}) }}
    />
  )
}

function OverviewStats({ accountId }: { accountId: number }) {
  const { data: overview, isLoading } = usePaperTradeOverview(accountId)
  const { data: navData } = usePaperTradeNav(accountId, 10)
  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spin />
      </div>
    )
  }
  const cash = overview?.cash
  const nav = cash?.nav
  const marketValue = (overview?.positions ?? []).reduce(
    (sum, p) => sum + Number(p.marketValue ?? 0),
    0,
  )
  const cumPnl =
    nav != null && cash?.cumInout != null ? Number(nav) - Number(cash.cumInout) : null
  // 当日盈亏 = 实时 nav − 最近一次快照 nav（当日 16:00 同步前，最近快照即昨收）
  const navPoints = navData?.items ?? []
  const prevNav = navPoints.length > 0 ? navPoints[navPoints.length - 1].nav : null
  const dayPnl = nav != null && prevNav != null ? Number(nav) - Number(prevNav) : null

  return (
    <div className="flex flex-wrap gap-x-10 gap-y-3">
      <Statistic
        title="总资产"
        value={nav == null ? '-' : formatAmount(Number(nav))}
        valueStyle={{ fontSize: 18 }}
      />
      <Statistic
        title="持仓市值"
        value={overview ? formatAmount(marketValue) : '-'}
        valueStyle={{ fontSize: 18 }}
      />
      <Statistic
        title="可用资金"
        value={cash?.available == null ? '-' : formatAmount(Number(cash.available))}
        valueStyle={{ fontSize: 18 }}
      />
      <PnlStatistic title="累计盈亏" pnl={cumPnl} />
      <PnlStatistic title="当日盈亏" pnl={dayPnl} />
    </div>
  )
}

export function AgentTradeRecords() {
  const agentKey = useAgentKey()
  const { data: accounts, isLoading } = useAdminPaperTradeAccounts()
  const agentAccount = accounts?.items.find((account) => account.agentKey === agentKey)

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spin />
      </div>
    )
  }
  if (!agentAccount) {
    return (
      <Card size="small">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="尚未绑定 Agent 专属账户，请在「配置」中指定"
        />
      </Card>
    )
  }

  return (
    <AgentAccountRecords accountId={agentAccount.id} accountName={agentAccount.name} />
  )
}

function AgentAccountRecords({ accountId, accountName }: { accountId: number; accountName: string }) {
  const { data: overview, isLoading } = usePaperTradeOverview(accountId)

  return (
    <Space direction="vertical" size="middle" className="w-full">
      <Card size="small" title={`资金概览 · ${accountName}`}>
        <OverviewStats accountId={accountId} />
      </Card>
      <Card size="small" title="当前持仓">
        <PaperTradePositions
          positions={overview?.positions ?? []}
          loading={isLoading}
          nav={overview?.cash?.nav}
        />
      </Card>
      <Card size="small" title="交易记录" styles={{ body: { paddingTop: 4 } }}>
        <Tabs
          size="small"
          items={[
            { key: 'orders', label: '委托', children: <PaperTradeOrdersPanel accountId={accountId} /> },
            {
              key: 'executions',
              label: '成交',
              children: <PaperTradeExecutionsPanel accountId={accountId} />,
            },
          ]}
        />
      </Card>
    </Space>
  )
}
