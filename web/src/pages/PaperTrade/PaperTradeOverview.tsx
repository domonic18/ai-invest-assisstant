import { InfoCircleOutlined } from '@ant-design/icons'
import { Card, Tooltip } from 'antd'
import type { ReactNode } from 'react'

import type { ApiPaperTradeCash } from '@ai-invest/shared'

import { changeColor, formatAmount, formatNumber } from '@/utils/formatters'

interface PaperTradeOverviewProps {
  cash?: ApiPaperTradeCash | null
  /** 当日盈亏（nav 差修正出入金，index 层计算）；null = 基准快照缺失不展示 */
  dayPnl: number | null
  /** 资金栏右侧操作区（账户选择器 + 账户配置入口） */
  children?: ReactNode
}

function Stat({
  title,
  value,
  color,
}: {
  title: ReactNode
  value: string
  color?: string
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-xs whitespace-nowrap text-white/50">{title}</span>
      <span className="text-base font-medium" style={color ? { color } : undefined}>
        {value}
      </span>
    </div>
  )
}

/** 资金账户栏（紧凑单行）：总资产 / 可用资金 / 当日盈亏 + 右侧账户操作区。 */
export function PaperTradeOverview({ cash, dayPnl, children }: PaperTradeOverviewProps) {
  return (
    <Card size="small">
      <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-2">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
          <Stat
            title="总资产"
            value={cash?.nav == null ? '-' : formatAmount(Number(cash.nav))}
          />
          <Stat
            title="可用资金"
            value={cash?.available == null ? '-' : formatAmount(Number(cash.available))}
          />
          <Stat
            title={
              dayPnl == null && cash?.nav != null ? (
                <span className="inline-flex items-center gap-1">
                  当日盈亏
                  <Tooltip title="账户首个交易日暂无昨日基准快照，盘后自动同步（约 16:00）后即可显示">
                    <InfoCircleOutlined className="text-white/40" />
                  </Tooltip>
                </span>
              ) : (
                '当日盈亏'
              )
            }
            value={dayPnl == null ? '-' : `${dayPnl >= 0 ? '+' : ''}${formatNumber(Number(dayPnl))}`}
            color={dayPnl == null ? undefined : changeColor(dayPnl)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      </div>
    </Card>
  )
}
