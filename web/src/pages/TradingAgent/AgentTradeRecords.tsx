/**
 * Agent 交易记录（模拟管理页 tab）：agent 专属账户的资金概览 + 委托/成交。
 *
 * 账户 id 从 admin 账户列表取 isAgent 行；委托/成交直接复用模拟盘页导出的
 * PaperTradeOrdersPanel / PaperTradeExecutionsPanel（含日期筛选与撤单）。
 */
import { Card, Empty, Space, Spin, Statistic } from 'antd'

import { formatAmount } from '@/utils/formatters'

import { PaperTradeExecutionsPanel, PaperTradeOrdersPanel } from '@/pages/PaperTrade/PaperTradeOrderHistory'
import { useAdminPaperTradeAccounts } from '@/hooks/usePaperTrade'
import { usePaperTradeOverview } from '@/hooks/usePaperTrade'

function OverviewStats({ accountId }: { accountId: number }) {
  const { data: overview, isLoading } = usePaperTradeOverview(accountId)
  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spin />
      </div>
    )
  }
  const cash = overview?.cash
  return (
    <div className="flex flex-wrap gap-x-10 gap-y-3">
      <Statistic
        title="总资产"
        value={cash?.nav == null ? '-' : formatAmount(Number(cash.nav))}
        valueStyle={{ fontSize: 18 }}
      />
      <Statistic
        title="可用资金"
        value={cash?.available == null ? '-' : formatAmount(Number(cash.available))}
        valueStyle={{ fontSize: 18 }}
      />
      <Statistic title="持仓标的" value={overview?.positions.length ?? 0} valueStyle={{ fontSize: 18 }} />
      <Statistic
        title="未结委托"
        value={overview?.unfinishedOrders.length ?? 0}
        valueStyle={{ fontSize: 18 }}
      />
    </div>
  )
}

export function AgentTradeRecords() {
  const { data: accounts, isLoading } = useAdminPaperTradeAccounts()
  const agentAccount = accounts?.items.find((account) => account.isAgent)

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
          description="尚未绑定 Agent 专属账户，请在「账户与配置」中指定"
        />
      </Card>
    )
  }

  return (
    <Space direction="vertical" size="middle" className="w-full">
      <Card size="small" title={`资金概览 · ${agentAccount.name}`}>
        <OverviewStats accountId={agentAccount.id} />
      </Card>
      <Card size="small" title="委托记录">
        <PaperTradeOrdersPanel accountId={agentAccount.id} />
      </Card>
      <Card size="small" title="成交记录">
        <PaperTradeExecutionsPanel accountId={agentAccount.id} />
      </Card>
    </Space>
  )
}
