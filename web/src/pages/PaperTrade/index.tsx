import { SettingOutlined } from '@ant-design/icons'
import { Badge, Button, Card, Col, Empty, Row, Select, Space, Spin, Tabs, Tag, Typography } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'

import {
  PaperTradeExecutionsPanel,
  PaperTradeOrdersPanel,
  SyncButton,
} from './PaperTradeOrderHistory'
import { PaperTradeOverview } from './PaperTradeOverview'
import { PaperTradePositions } from './PaperTradePositions'
import { TradingPanel } from './TradingPanel'
import type { OrderPrefill } from './TradingPanel'
import { AccountManagerModal } from './AccountManagerModal'
import { NavChart } from './NavChart'
import {
  usePaperTradeAccounts,
  usePaperTradeNav,
  usePaperTradeOverview,
  usePaperTradeSyncAction,
} from '@/hooks/usePaperTrade'
import { bjNow } from '@/utils/beijing'
import { DATE_FORMAT } from '@/utils/formatters'

/** 未配置引导卡：无账户配置或服务端未启用模拟盘网关时展示使用方法。 */
function GuideCard({ onManage }: { onManage: () => void }) {
  return (
    <Card size="small">
      <Empty description="模拟交易尚未配置账户">
        <Space direction="vertical" size={4}>
          <Typography.Text type="secondary">
            1. 访问 myquant.cn（掘金量化）注册并登录
          </Typography.Text>
          <Typography.Text type="secondary">
            2. 下载安装掘金客户端，登录后在「交易」→「账户管理」中添加仿真账户
          </Typography.Text>
          <Typography.Text type="secondary">
            3. 在客户端获取仿真账户的 token 与账户 ID，点击下方「账户配置」录入
          </Typography.Text>
          <Typography.Link
            href="https://www.myquant.cn/docs2/operatingInstruction/trading/%E4%BB%BF%E7%9C%9F%E4%BA%A4%E6%98%93.html"
            target="_blank"
          >
            查看掘金仿真交易官方图文教程
          </Typography.Link>
          <Button type="primary" icon={<SettingOutlined />} onClick={onManage} className="mt-2">
            账户配置
          </Button>
        </Space>
      </Empty>
    </Card>
  )
}

/** 模拟交易页（同花顺式布局）：资金账户栏 / [下单面板 | 持仓·委托·成交 tabs] / 净值曲线。 */
export function PaperTrade() {
  const accountsQuery = usePaperTradeAccounts()
  const accounts = useMemo(() => accountsQuery.data?.items ?? [], [accountsQuery.data])
  const [accountId, setAccountId] = useState<number | undefined>(undefined)
  const [managerOpen, setManagerOpen] = useState(false)
  const [prefill, setPrefill] = useState<OrderPrefill | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const { syncRun, pending: syncPending } = usePaperTradeSyncAction()

  // 持仓行「买入/卖出」→ 回填左侧下单卡
  const handleTrade = (item: OrderPrefill) => {
    setPrefill(item)
  }

  // 账户列表变化时保持选中项有效（删除当前账户后回落到首个账户）
  useEffect(() => {
    if (accounts.length === 0) {
      setAccountId(undefined)
    } else if (accountId == null || !accounts.some((a) => a.id === accountId)) {
      setAccountId(accounts[0].id)
    }
  }, [accounts, accountId])

  const overviewQuery = usePaperTradeOverview(accountId)
  const navQuery = usePaperTradeNav(accountId, 30)

  if (accountsQuery.isLoading) {
    return (
      <div className="p-4 flex justify-center py-24">
        <Spin />
      </div>
    )
  }

  if (accounts.length === 0) {
    return (
      <div className="p-4">
        <GuideCard onManage={() => setManagerOpen(true)} />
        <AccountManagerModal open={managerOpen} onClose={() => setManagerOpen(false)} />
      </div>
    )
  }

  const account = accounts.find((a) => a.id === accountId)
  const overview = overviewQuery.data
  const pageReady = account != null && overview != null && overview.enabled

  // 当日盈亏 = 实时 nav - 最近一个「今日之前」的快照 nav - 当日出入金
  const todayStr = bjNow().format(DATE_FORMAT)
  const prevPoint = [...(navQuery.data?.items ?? [])]
    .reverse()
    .find((p) => p.tradeDate < todayStr)
  const dayPnl =
    overview?.cash?.nav != null && prevPoint?.nav != null
      ? overview.cash.nav - prevPoint.nav - (overview.cash.lastInout ?? 0)
      : null

  const unfinished = overview?.unfinishedOrders.length ?? 0
  const accountBar = (
    <>
      <Select
        value={accountId}
        onChange={setAccountId}
        style={{ minWidth: 180 }}
        options={accounts.map((a) => ({
          value: a.id,
          label: (
            <span className="flex items-center gap-2">
              {a.name}
              {a.agentKey && <Tag color="gold">Agent</Tag>}
              {!a.isEnabled && <Tag>已停用</Tag>}
            </span>
          ),
        }))}
      />
      {account?.counterAccountId && (
        <Typography.Text type="secondary" className="text-xs">
          {account.counterAccountId}
        </Typography.Text>
      )}
      <Button icon={<SettingOutlined />} onClick={() => setManagerOpen(true)}>
        账户配置
      </Button>
    </>
  )

  return (
    <div className="p-4 space-y-4">
      {!pageReady ? (
        overviewQuery.isLoading ? (
          <div className="flex justify-center py-16">
            <Spin />
          </div>
        ) : (
          <GuideCard onManage={() => setManagerOpen(true)} />
        )
      ) : (
        <>
          <PaperTradeOverview cash={overview.cash} dayPnl={dayPnl}>
            {accountBar}
          </PaperTradeOverview>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8} xxl={7}>
              <div ref={panelRef}>
                <TradingPanel
                  account={account}
                  cashAvailable={overview.cash?.available ?? null}
                  positions={overview.positions}
                  prefill={prefill}
                  onPrefillConsumed={() => setPrefill(null)}
                />
              </div>
            </Col>
            <Col xs={24} lg={16} xxl={17}>
              <Card
                size="small"
                styles={{ body: { paddingTop: 8 } }}
                extra={
                  <span className="flex items-center gap-3">
                    {unfinished > 0 && (
                      <span className="text-xs text-white/60">
                        未结 <Badge count={unfinished} size="small" />
                      </span>
                    )}
                    <SyncButton
                      pending={syncPending}
                      onClick={() => void syncRun(account.id)}
                    />
                  </span>
                }
              >
                <Tabs
                  defaultActiveKey="positions"
                  items={[
                    {
                      key: 'positions',
                      label: '持仓',
                      children: (
                        <PaperTradePositions
                          positions={overview.positions}
                          loading={overviewQuery.isFetching}
                          nav={overview.cash?.nav ?? null}
                          onTrade={handleTrade}
                        />
                      ),
                    },
                    {
                      key: 'orders',
                      label: unfinished > 0 ? `委托（${unfinished} 未结）` : '委托',
                      children: (
                        <PaperTradeOrdersPanel
                          accountId={account.id}
                          onSynced={() => syncRun(account.id)}
                        />
                      ),
                    },
                    {
                      key: 'executions',
                      label: '成交',
                      children: <PaperTradeExecutionsPanel accountId={account.id} />,
                    },
                  ]}
                />
              </Card>
            </Col>
          </Row>
          <NavChart items={navQuery.data?.items ?? []} loading={navQuery.isLoading} />
        </>
      )}
      <AccountManagerModal open={managerOpen} onClose={() => setManagerOpen(false)} />
    </div>
  )
}
