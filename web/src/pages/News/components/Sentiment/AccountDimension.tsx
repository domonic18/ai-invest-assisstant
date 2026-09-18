/** 账号维度卡：统计窗口内多空分布 + 按日时序 + 最新判断，点击切换到该账号时间线。
 * 摘要区块可整体收起（持久化记忆），避免追踪账号增多后挤压下方视频信息流。 */

import { Button, Card, Empty, Spin, theme } from 'antd'
import { DownOutlined } from '@ant-design/icons'

import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { formatRelativeTime, fallHex, riseHex } from '@/utils/formatters'
import { useColorScheme, useSettingsStore } from '@/stores/settings'

import { StanceBadge } from './StanceBadge'
import { StanceDailyBars } from './StanceDailyBars'
import { mergeAccountDaily, sumStance } from './daily'
import { CATEGORY_LABELS } from './labels'

interface AccountDimensionProps {
  accounts: ApiSocialAccountCard[]
  isLoading: boolean
  selectedId: number | null
  onSelect: (account: ApiSocialAccountCard) => void
}

export function AccountDimension({
  accounts,
  isLoading,
  selectedId,
  onSelect,
}: AccountDimensionProps) {
  useColorScheme()
  const { token } = theme.useToken()
  const collapsed = useSettingsStore((s) => s.sentimentSummaryCollapsed)
  const toggleCollapsed = useSettingsStore((s) => s.toggleSentimentSummaryCollapsed)

  if (!isLoading && accounts.length === 0) {
    return <Empty description="暂无追踪账号数据" />
  }

  const merged = mergeAccountDaily(accounts)
  const totals = sumStance(merged)

  return (
    <Spin spinning={isLoading}>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">大V情绪摘要</span>
          <span className="text-xs text-gray-500">{accounts.length} 位</span>
          <Button
            type="text"
            size="small"
            className="ml-auto"
            aria-label={collapsed ? '展开大V情绪摘要' : '收起大V情绪摘要'}
            icon={<DownOutlined rotate={collapsed ? -90 : 0} />}
            onClick={toggleCollapsed}
          />
        </div>

        {!collapsed && (
          <>
            {accounts.length > 0 && (
              <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 flex items-center gap-3 flex-wrap">
                <span className="text-xs font-semibold shrink-0">全账号情绪时序</span>
                <span className="text-xs shrink-0" style={{ color: riseHex() }}>
                  多 {totals.bullish}
                </span>
                <span className="text-xs shrink-0" style={{ color: fallHex() }}>
                  空 {totals.bearish}
                </span>
                <span className="text-xs opacity-60 shrink-0">中 {totals.neutral}</span>
                <div className="flex-1 min-w-[240px]">
                  <StanceDailyBars rows={merged} height={32} showDayLabel />
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {accounts.map((account) => (
                <Card
                  key={account.id}
                  size="small"
                  hoverable
                  variant="borderless"
                  onClick={() => onSelect(account)}
                  className="cursor-pointer"
                  style={
                    selectedId === account.id
                      ? { border: `1px solid ${token.colorPrimary}` }
                      : undefined
                  }
                  styles={{ body: { padding: '10px 12px' } }}
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate min-w-0">
                        {account.alias}
                      </span>
                      {account.latestStance && (
                        <StanceBadge
                          stance={account.latestStance}
                          confidence={account.latestConfidence}
                        />
                      )}
                      <span className="ml-auto text-xs opacity-40 shrink-0">
                        {CATEGORY_LABELS[account.category] ?? account.category}
                      </span>
                    </div>

                    <div className="flex items-center gap-2.5 text-xs">
                      <span style={{ color: riseHex() }}>多 {account.bullishCount}</span>
                      <span style={{ color: fallHex() }}>空 {account.bearishCount}</span>
                      <span className="opacity-60">中 {account.neutralCount}</span>
                      <span className="flex-1 min-w-[80px] flex justify-end">
                        <StanceDailyBars rows={account.daily} height={20} />
                      </span>
                    </div>

                    {account.latestSummary && (
                      <div className="text-xs opacity-70 line-clamp-2">
                        {account.latestSummary}
                      </div>
                    )}
                    <div className="text-xs opacity-40">
                      {account.lastPostAt
                        ? `最新发布 ${formatRelativeTime(account.lastPostAt)}`
                        : '暂无发布'}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}
      </div>
    </Spin>
  )
}
