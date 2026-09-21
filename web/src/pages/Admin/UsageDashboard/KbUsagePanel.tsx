import {
  Card,
  Col,
  DatePicker,
  Descriptions,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Typography,
} from 'antd'
import { useState } from 'react'
import type { Dayjs } from 'dayjs'

import type { ApiKbUsageTokenItem } from '@ai-invest/shared'

import { useKbSources, useKbUsage } from '@/hooks/useAdminKb'

const FEATURE_LABELS: Record<string, string> = {
  kb_clean: '清洗',
  kb_extract: '抽取',
  kb_vision: '视觉',
  kb_embed: '嵌入',
}

const TOKEN_COLUMNS = [
  { title: '分项', dataIndex: 'feature', render: (v: string) => FEATURE_LABELS[v] ?? v },
  { title: '模型', dataIndex: 'modelName', render: (v: string | null) => v ?? '—' },
  {
    title: '调用次数',
    dataIndex: 'calls',
    align: 'right' as const,
    render: (v: number) => v.toLocaleString('zh-CN'),
  },
  {
    title: 'Prompt tokens',
    dataIndex: 'promptTokens',
    align: 'right' as const,
    render: (v: number) => v.toLocaleString('zh-CN'),
  },
  {
    title: '补全 tokens',
    dataIndex: 'completionTokens',
    align: 'right' as const,
    render: (v: number) => v.toLocaleString('zh-CN'),
  },
  {
    title: '合计 tokens',
    dataIndex: 'totalTokens',
    align: 'right' as const,
    render: (v: number) => v.toLocaleString('zh-CN'),
  },
  {
    title: '预估费用（元）',
    dataIndex: 'estimatedCost',
    align: 'right' as const,
    render: (v: number | null) => (v != null ? v.toFixed(4) : '—'),
  },
]

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.round(seconds % 60)
  return `${h}时${String(m).padStart(2, '0')}分${String(s).padStart(2, '0')}秒`
}

function formatTokens(n: number): string {
  return `${n.toLocaleString('zh-CN')}（约 ${(n / 10_000).toFixed(1)} 万）`
}

export function KbUsagePanel() {
  const [sourceId, setSourceId] = useState<number | null>(null)
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const { data: sources } = useKbSources()
  const dateFrom = range?.[0]?.format('YYYY-MM-DD') ?? null
  const dateTo = range?.[1]?.format('YYYY-MM-DD') ?? null
  const { data: usage, isLoading } = useKbUsage(sourceId, dateFrom, dateTo)
  const asrHours = usage ? usage.asr.audioSeconds / 3600 : 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <Typography.Text type="secondary" className="!mt-1 !mb-0 text-xs">
          知识库构建成本核算：kb_* token 分项 + ASR 按时长计费（CNY，预估 vs 实际对照）
        </Typography.Text>
        <Space wrap>
          <Select
            value={sourceId ?? undefined}
            onChange={(id) => setSourceId(id ?? null)}
            options={(sources ?? []).map((s) => ({ value: s.id, label: s.name }))}
            allowClear
            placeholder="全部知识库"
            style={{ width: 220 }}
          />
          <DatePicker.RangePicker
            value={range}
            onChange={(value) => setRange(value as [Dayjs | null, Dayjs | null] | null)}
          />
        </Space>
      </div>

      <Row gutter={[12, 12]}>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={isLoading}>
            <Statistic
              title="合计费用（元）"
              value={usage?.totalCost ?? 0}
              precision={4}
              suffix={usage ? <span className="text-xs">{usage.currency}</span> : null}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={isLoading}>
            <Statistic
              title="ASR 实际时长（小时）"
              value={asrHours}
              precision={1}
              suffix={usage?.asr.cost ? <span className="text-xs">¥{usage.asr.cost}</span> : null}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={isLoading}>
            <Statistic title="已转写素材" value={usage?.asr.mediaCount ?? 0} suffix="个" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={isLoading}>
            <Statistic
              title="清洗 token 预估 / 实际"
              value={usage?.cleanTokensPredicted ?? 0}
              formatter={() => (
                <span className="font-mono text-lg">
                  {(usage?.cleanTokensPredicted ?? 0).toLocaleString('zh-CN')}
                  <span className="text-[#8a8f98]"> / </span>
                  {(usage?.cleanTokensActual ?? 0).toLocaleString('zh-CN')}
                </span>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" title="token 分项（清洗 → 抽取 → 视觉 → 嵌入）" loading={isLoading}>
        <Table<ApiKbUsageTokenItem>
          rowKey={(r) => `${r.feature}:${r.modelName ?? ''}`}
          columns={TOKEN_COLUMNS}
          dataSource={usage?.tokenItems ?? []}
          pagination={false}
          size="small"
        />
      </Card>

      {usage && (
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <Card variant="borderless" title="转写（ASR，按时长计费）" size="small">
              <Descriptions size="small" column={1} bordered>
                <Descriptions.Item label="实际音频时长">
                  {formatDuration(usage.asr.audioSeconds)}
                </Descriptions.Item>
                <Descriptions.Item label="登记时长（预估口径）">
                  {formatDuration(usage.asr.estimatedSeconds)}
                </Descriptions.Item>
                <Descriptions.Item label="转写单价">
                  {usage.asr.costPerHour != null
                    ? `${usage.asr.costPerHour} 元/小时`
                    : '未配置'}
                </Descriptions.Item>
                <Descriptions.Item label="转写费用">
                  {usage.asr.cost != null ? `${usage.asr.cost} 元` : '—'}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card variant="borderless" title="预估 vs 实际对照" size="small">
              <Descriptions size="small" column={1} bordered>
                <Descriptions.Item label="清洗 token 预估（时长折算）">
                  {formatTokens(usage.cleanTokensPredicted)}
                </Descriptions.Item>
                <Descriptions.Item label="清洗 token 台账实际">
                  {formatTokens(usage.cleanTokensActual)}
                </Descriptions.Item>
                <Descriptions.Item label="视觉费用（vlmPerImage × 调用次数）">
                  {usage.tokenItems
                    .filter((i) => i.feature === 'kb_vision')
                    .map((i) =>
                      i.estimatedCost != null ? `${i.estimatedCost} 元` : '未配置单价'
                    )
                    .join('，') || '—'}
                </Descriptions.Item>
                <Descriptions.Item label="合计">
                  {usage.totalCost} {usage.currency}（未配置单价的项目不计入）
                </Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
