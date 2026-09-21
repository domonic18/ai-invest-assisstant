import { Card, DatePicker, Descriptions, Select, Space, Table, Typography } from 'antd'
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
  return `${h}时${String(m).padStart(2, '0')}分${String(s).padStart(2, '0')}秒（${(seconds / 3600).toFixed(1)} 小时）`
}

function formatTokens(n: number): string {
  return `${n.toLocaleString('zh-CN')}（约 ${(n / 10_000).toFixed(1)} 万）`
}

export function UsagePanel() {
  const [sourceId, setSourceId] = useState<number | null>(null)
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const { data: sources } = useKbSources()
  const dateFrom = range?.[0]?.format('YYYY-MM-DD') ?? null
  const dateTo = range?.[1]?.format('YYYY-MM-DD') ?? null
  const { data: usage, isLoading } = useKbUsage(sourceId, dateFrom, dateTo)

  return (
    <Card type="inner" title="建库用量" style={{ marginTop: 24 }}>
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          value={sourceId ?? undefined}
          onChange={(id) => setSourceId(id ?? null)}
          options={(sources ?? []).map((s) => ({ value: s.id, label: s.name }))}
          allowClear
          placeholder="全部知识库"
          style={{ width: 240 }}
        />
        <DatePicker.RangePicker
          value={range}
          onChange={(value) => setRange(value as [Dayjs | null, Dayjs | null] | null)}
        />
      </Space>

      <Table<ApiKbUsageTokenItem>
        rowKey={(r) => `${r.feature}:${r.modelName ?? ''}`}
        columns={TOKEN_COLUMNS}
        dataSource={usage?.tokenItems ?? []}
        loading={isLoading}
        pagination={false}
        size="small"
        style={{ marginBottom: 16 }}
      />

      {usage && (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Descriptions title="转写（ASR，按时长计费）" size="small" column={2} bordered>
            <Descriptions.Item label="已转写素材">
              {usage.asr.mediaCount} 个
            </Descriptions.Item>
            <Descriptions.Item label="转写单价">
              {usage.asr.costPerHour != null
                ? `${usage.asr.costPerHour} 元/小时`
                : '未配置'}
            </Descriptions.Item>
            <Descriptions.Item label="实际音频时长">
              {formatDuration(usage.asr.audioSeconds)}
            </Descriptions.Item>
            <Descriptions.Item label="登记时长（预估口径）">
              {formatDuration(usage.asr.estimatedSeconds)}
            </Descriptions.Item>
            <Descriptions.Item label="转写费用">
              {usage.asr.cost != null ? `${usage.asr.cost} 元` : '—'}
            </Descriptions.Item>
          </Descriptions>

          <Descriptions title="预估 vs 实际对照" size="small" column={2} bordered>
            <Descriptions.Item label="清洗 token 预估（时长折算）">
              {formatTokens(usage.cleanTokensPredicted)}
            </Descriptions.Item>
            <Descriptions.Item label="清洗 token 台账实际">
              {formatTokens(usage.cleanTokensActual)}
            </Descriptions.Item>
          </Descriptions>

          <Typography.Text strong>
            合计费用：{usage.totalCost} {usage.currency}（转写 + 视觉估算；未配置单价的项目不计入）
          </Typography.Text>
        </Space>
      )}
    </Card>
  )
}
