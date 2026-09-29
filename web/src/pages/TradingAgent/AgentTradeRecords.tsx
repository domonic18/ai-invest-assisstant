/**
 * Agent 持仓与交易（智体中枢页 tab，D29 重构）：agent 专属账户的资金
 * 五指标（总资产/持仓市值/可用资金/累计盈亏/当日盈亏）+ 当前持仓 +
 * 委托/成交记录（日期选择即历史查询）。
 *
 * 账户 id 从 admin 账户列表取 agentKey 绑定行；持仓表复用模拟盘页导出的
 * PaperTradePositions（不传 onTrade，agent 账户人工不在此直接下单）；
 * 累计盈亏 = nav − cumInout（百分比分母 cumInout）；当日盈亏 = 实时 nav −
 * 「今日之前最近快照」nav − 当日出入金（与模拟盘页同口径，前端算，缺快照
 * 显示 -）。盈亏红涨绿跌 + 括号百分比（同花顺口径）。
 */
import { Card, Empty, Space, Spin, Statistic, Tabs } from 'antd'

import { PaperTradeExecutionsPanel, PaperTradeOrdersPanel } from '@/pages/PaperTrade/PaperTradeOrderHistory'
import { PaperTradePositions } from '@/pages/PaperTrade/PaperTradePositions'
import {
  useAdminPaperTradeAccounts,
  usePaperTradeNav,
  usePaperTradeOverview,
} from '@/hooks/usePaperTrade'
import { bjNow } from '@/utils/beijing'
import { changeHex, DATE_FORMAT, formatAmount, formatNumber, formatPercent } from '@/utils/formatters'

import { useAgentKey } from './agentKeyContext'

function PnlStatistic({
  title,
  pnl,
  pct,
}: {
  title: string
  pnl: number | null
  pct: number | null
}) {
  const text =
    pnl == null
      ? '-'
      : `${pnl >= 0 ? '+' : ''}${formatNumber(pnl)}${pct != null ? ` (${formatPercent(pct)})` : ''}`
  return (
    <Statistic
      title={title}
      value={text}
      valueStyle={{ fontSize: 18, ...(pnl != null ? { color: changeHex(pnl) } : {}) }}
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
  const cumInout = cash?.cumInout != null ? Number(cash.cumInout) : null
  const cumPnl = nav != null && cumInout != null ? Number(nav) - cumInout : null
  const cumPct =
    cumPnl != null && cumInout != null && Math.abs(cumInout) > 0
      ? (cumPnl / cumInout) * 100
      : null
  // 当日盈亏 = 实时 nav − 前一快照 nav − 两快照间出入金增量（lastInout 是
  // 账户最后一笔出入金而非当日，误用会把历史入金全数计成亏损）
  const todayStr = bjNow().format(DATE_FORMAT)
  const prevPoint = [...(navData?.items ?? [])]
    .reverse()
    .find((p) => p.tradeDate < todayStr)
  const dayBase =
    prevPoint?.nav != null
      ? prevPoint.nav + (cumInout ?? 0) - (prevPoint.cumInout ?? 0)
      : null
  const dayPnl = nav != null && dayBase != null ? Number(nav) - dayBase : null
  const dayPct =
    dayPnl != null && dayBase != null && Math.abs(dayBase) > 0
      ? (dayPnl / dayBase) * 100
      : null

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
      <PnlStatistic title="累计盈亏" pnl={cumPnl} pct={cumPct} />
      <PnlStatistic title="当日盈亏" pnl={dayPnl} pct={dayPct} />
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
          defaultActiveKey="executions"
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
