import { Card, Col, Row, Statistic } from 'antd'

import type { ApiPaperTradeCash } from '@ai-invest/shared'

import { changeColor, formatAmount, formatNumber } from '@/utils/formatters'

interface PaperTradeOverviewProps {
  cash?: ApiPaperTradeCash | null
  /** 当日盈亏（nav 差修正出入金，index 层计算）；null = 基准快照缺失不展示 */
  dayPnl: number | null
}

export function PaperTradeOverview({ cash, dayPnl }: PaperTradeOverviewProps) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={8}>
        <Card size="small">
          <Statistic
            title="总资产"
            value={cash?.nav ?? undefined}
            precision={2}
            formatter={(value) => (value == null ? '-' : formatAmount(Number(value)))}
          />
        </Card>
      </Col>
      <Col xs={24} sm={8}>
        <Card size="small">
          <Statistic
            title="可用资金"
            value={cash?.available ?? undefined}
            precision={2}
            formatter={(value) => (value == null ? '-' : formatAmount(Number(value)))}
          />
        </Card>
      </Col>
      <Col xs={24} sm={8}>
        <Card size="small">
          <Statistic
            title="当日盈亏"
            value={dayPnl ?? undefined}
            precision={2}
            formatter={(value) => (value == null ? '-' : formatNumber(Number(value)))}
            valueStyle={dayPnl != null ? { color: changeColor(dayPnl) } : undefined}
          />
        </Card>
      </Col>
    </Row>
  )
}
