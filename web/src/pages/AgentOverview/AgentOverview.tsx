/**
 * 智能中枢（Agent Hub 总览页，路由 /trading-agent index，仅 admin）：
 * 电路脉冲主板 REV4——左画布 = PCB 主板（芯片五态 + 资源站心跳 + 日内业务
 * 时间线逻辑分析仪），右栏 = 拟人化实时决策流（最多 8 张卡）；点击芯片过滤右栏。
 * 决策流可收起/展开（右上角按钮，localStorage 记忆）：收起后主板占满整行、
 * SVG 按宽度铺满放大（fillWidth），观测轮询保持不断（主板 ORD/ACK 丝印依赖）。
 * 整页 h-full 约束一屏：主板 SVG 在剩余高度内等比缩放，首屏 isLoading 渲染骨架。
 * /agents 聚合 30s 轮询；决策流沿用盘中 15s 快轮询（useLiveAgentObservations）。
 * Agent 管理（增删改）收进右上角图标按钮弹出的对话框。
 */
import { PicRightOutlined, SettingOutlined } from '@ant-design/icons'
import { Button, Modal, Tooltip, Typography } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import { useCeleryQueues } from '@/hooks/useCeleryQueues'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { useSystemStatus } from '@/hooks/useSystemStatus'
import { useAgentOverview, useLiveAgentObservations } from '@/hooks/useTradingAgent'
import { marketSession } from '@/pages/PaperTrade/tradingRules'
import { bjNow } from '@/utils/beijing'

import { CircuitBoard } from './circuit/CircuitBoard'
import { BoardSkeleton } from './circuit/BoardSkeleton'
import { beijingMinutes } from './circuit/timeAxis'
import { NarrativeFeed } from './feed/NarrativeFeed'
import { AgentManageList } from './AgentManageList'

const REFRESH_INTERVAL_MS = 30_000
const FEED_COLLAPSED_KEY = 'agentHub.feedCollapsed'

export function AgentOverview() {
  const { data, isLoading } = useAgentOverview({ refetchInterval: REFRESH_INTERVAL_MS })
  const { data: systemStatus } = useSystemStatus()
  const { data: celeryQueues } = useCeleryQueues()
  const reducedMotion = usePrefersReducedMotion()
  const items = data?.items ?? []
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [manageOpen, setManageOpen] = useState(false)
  const [feedCollapsed, setFeedCollapsed] = useState(
    () => localStorage.getItem(FEED_COLLAPSED_KEY) === '1',
  )

  const toggleFeed = () =>
    setFeedCollapsed((collapsed) => {
      localStorage.setItem(FEED_COLLAPSED_KEY, collapsed ? '0' : '1')
      return !collapsed
    })

  // 右栏展示 agent：选中（非 off）→ 首个 active（沿用旧决策流回退口径）
  const feedAgent =
    items.find((item) => item.profile.agentKey === selectedKey && item.runtimeState !== 'off') ??
    items.find((item) => item.profile.status === 'active') ??
    null
  const { data: feed, isLoading: feedLoading } = useLiveAgentObservations(
    feedAgent?.profile.agentKey ?? null,
  )

  // 最新委托：柜台 ORD/ACK 丝印 + LA 红标（execute 行里最新一笔）
  const latestExecute = (feed?.items ?? []).find((item) => item.action === 'execute')
  const latestOrder = latestExecute
    ? {
        agentKey: latestExecute.agentKey,
        volume: latestExecute.orderVolume,
        price: latestExecute.price,
        ackTime: dayjs(latestExecute.tickTime).format('HH:mm:ss'),
        minutes: beijingMinutes(latestExecute.tickTime) ?? 0,
      }
    : null

  const now = bjNow()
  const session = marketSession(now)
  const powerOk = systemStatus?.overall !== 'degraded'
  const sessionText = { open: '盘中实时', break: '午间休市', pre: '盘前', closed: '盘后' }[session]

  return (
    <div className="flex min-h-0 flex-col gap-3 lg:h-full">
      <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1">
        <Typography.Title level={4} className="!mb-0 w-full sm:w-auto">
          智能中枢 · <span className="text-[#34d399]">电路脉冲主板</span>
        </Typography.Title>
        <span className="rounded border border-[rgba(52,211,153,.4)] px-1.5 py-px text-[10px] tracking-wider text-[#34d399]">
          REV 4.0
        </span>
        <Typography.Text type="secondary" className="hidden text-xs lg:inline">
          芯片五态 × 资源站心跳 × 日内业务时间线：实线=已发生 · 虚线=计划窗 · 红标=委托事件
        </Typography.Text>
        <span className="ml-auto inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-[rgba(94,106,210,.4)] bg-[rgba(94,106,210,.10)] px-3 py-1 text-xs text-[#c7cbf5]">
          <i className="h-[7px] w-[7px] animate-pulse rounded-full bg-[#2ea043] shadow-[0_0_8px_rgba(46,160,67,.9)]" />
          {sessionText} {now.format('HH:mm')} · 主板供电{powerOk ? '正常' : '降级'}
        </span>
        <Tooltip title={feedCollapsed ? '展开决策流' : '收起决策流'}>
          <Button
            type="text"
            aria-label={feedCollapsed ? '展开决策流' : '收起决策流'}
            icon={<PicRightOutlined />}
            onClick={toggleFeed}
          />
        </Tooltip>
        <Tooltip title="Agent 管理">
          <Button
            type="text"
            aria-label="Agent 管理"
            icon={<SettingOutlined />}
            onClick={() => setManageOpen(true)}
          />
        </Tooltip>
      </div>

      {/* 移动端纵向堆叠（主板按 viewBox 比例占位），lg 起恢复一屏双栏 */}
      <div className="flex flex-col gap-5 lg:min-h-0 lg:flex-1 lg:flex-row lg:items-stretch">
        <div className="flex aspect-[1140/800] w-full min-w-0 flex-none flex-col lg:aspect-auto lg:min-h-0 lg:flex-1">
          {isLoading ? (
            <BoardSkeleton />
          ) : (
            <CircuitBoard
              items={items}
              selectedKey={selectedKey}
              onSelectAgent={setSelectedKey}
              systemStatus={systemStatus}
              celeryQueues={celeryQueues}
              latestOrder={latestOrder}
              today={now.format('YYYY-MM-DD')}
              nowMinutes={now.hour() * 60 + now.minute()}
              reducedMotion={reducedMotion}
              fillWidth={feedCollapsed}
            />
          )}
        </div>
        {!feedCollapsed && (
          <NarrativeFeed agent={feedAgent} feed={feed} feedLoading={feedLoading || isLoading} />
        )}
      </div>

      <Modal
        title="Agent 管理"
        open={manageOpen}
        footer={null}
        width={640}
        onCancel={() => setManageOpen(false)}
      >
        <AgentManageList items={items} isLoading={isLoading} />
      </Modal>
    </div>
  )
}
