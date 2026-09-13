import { Card, Col, Row, Statistic } from 'antd'

import type { ApiCollectorHealthOverview } from '@ai-invest/shared'

import { domainLabel, rateText, STATUS_META } from './constants'

interface OverviewCardsProps {
  overview: ApiCollectorHealthOverview
}

export function OverviewCards({ overview }: OverviewCardsProps) {
  const { healthScore, counts, successRate24h } = overview

  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="健康分"
              value={healthScore}
              precision={0}
              suffix="/ 100"
              valueStyle={{
                color: healthScore >= 90 ? '#2ea043' : healthScore >= 60 ? '#d29922' : '#f85149',
              }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="进行中故障"
              value={counts.critical}
              valueStyle={{ color: counts.critical > 0 ? '#f85149' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="静默（超 7 天无成功）"
              value={counts.silent}
              valueStyle={{ color: counts.silent > 0 ? '#f85149' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="24h 成功率"
              value={rateText(successRate24h)}
              valueStyle={{ color: successRate24h != null && successRate24h < 0.8 ? '#d29922' : undefined }}
            />
          </Card>
        </Col>
      </Row>

      <Card size="small" title="按数据域概览">
        <Row gutter={[12, 12]}>
          {overview.domains.map((d) => (
            <Col xs={12} sm={8} md={6} lg={3} key={d.domain}>
              <div className="rounded border border-gray-200 p-2">
                <div className="text-sm font-medium mb-1">{domainLabel(d.domain)}</div>
                <StatusDots domain={d} />
              </div>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  )
}

function StatusDots({ domain }: { domain: ApiCollectorHealthOverview['domains'][number] }) {
  const entries = [
    { key: 'healthy', count: domain.healthy },
    { key: 'degraded', count: domain.degraded },
    { key: 'critical', count: domain.critical },
    { key: 'silent', count: domain.silent },
  ] as const
  const visible = entries.filter((e) => e.count > 0)
  if (visible.length === 0) {
    return <span className="text-xs text-gray-400">无实例</span>
  }
  return (
    <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-xs">
      {visible.map((e) => (
        <span key={e.key} style={{ color: STATUS_META[e.key as keyof typeof STATUS_META].color }}>
          {STATUS_META[e.key as keyof typeof STATUS_META].label} {e.count}
        </span>
      ))}
    </div>
  )
}
