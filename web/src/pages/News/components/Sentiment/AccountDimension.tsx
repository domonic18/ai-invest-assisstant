/** 账号维度卡：追踪账号近 7 日多空分布 + 最新判断，点击切换到该账号时间线。 */

import { Card, Empty, Spin, theme } from 'antd'

import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { formatRelativeTime, fallHex, riseHex } from '@/utils/formatters'
import { useSocialAccountCards } from '@/hooks/useSocialSentiment'
import { useColorScheme } from '@/stores/settings'

import { StanceBadge } from './StanceBadge'
import { CATEGORY_LABELS } from './labels'

interface AccountDimensionProps {
  selectedId: number | null
  onSelect: (account: ApiSocialAccountCard) => void
}

export function AccountDimension({ selectedId, onSelect }: AccountDimensionProps) {
  useColorScheme()
  const { token } = theme.useToken()
  const { data, isLoading } = useSocialAccountCards()
  const accounts = data?.accounts ?? []

  if (!isLoading && accounts.length === 0) {
    return <Empty description="暂无追踪账号数据" />
  }

  return (
    <Spin spinning={isLoading}>
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
                <span className="opacity-50">7日</span>
                <span style={{ color: riseHex() }}>多 {account.bullishCount7d}</span>
                <span style={{ color: fallHex() }}>空 {account.bearishCount7d}</span>
                <span className="opacity-60">中 {account.neutralCount7d}</span>
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
    </Spin>
  )
}
