import { Alert, Drawer, Select, Space, Spin, Table, Tag, Typography } from 'antd'
import { useState } from 'react'

import { useChainCompare } from '@/hooks/useChain'
import type { ChainCompareMetricChange, ChainVersionSummary } from '@ai-invest/shared'

interface VersionCompareDrawerProps {
  open: boolean
  versions: ChainVersionSummary[]
  defaultBaseId: number | null
  defaultTargetId: number | null
  onClose: () => void
}

const METRIC_FIELD_LABELS: Record<string, string> = {
  avg_gross_margin: '平均毛利率',
  revenue_growth: '营收增长',
  rd_ratio: '研发占比',
  bargaining_power: '议价能力',
  localization_rate: '国产化率',
}

export function VersionCompareDrawer({
  open,
  versions,
  defaultBaseId,
  defaultTargetId,
  onClose,
}: VersionCompareDrawerProps) {
  const successVersions = versions.filter((v) => v.status === 'success')
  const [baseId, setBaseId] = useState<number | null>(defaultBaseId)
  const [targetId, setTargetId] = useState<number | null>(defaultTargetId)

  const effectiveBase = baseId ?? defaultBaseId
  const effectiveTarget = targetId ?? defaultTargetId
  const { data, isLoading, error } = useChainCompare(
    open ? effectiveBase : null,
    open ? effectiveTarget : null
  )

  const versionOptions = successVersions.map((v) => ({
    value: v.id,
    label: `v${v.versionNo} · ${new Date(v.createdAt).toLocaleString('zh-CN')}`,
  }))

  const metricColumns = [
    { title: '环节', dataIndex: 'nodeName', key: 'nodeName' },
    {
      title: '指标',
      dataIndex: 'field',
      key: 'field',
      render: (field: string) => METRIC_FIELD_LABELS[field] ?? field,
    },
    {
      title: `v${data?.baseVersion.versionNo ?? '—'}`,
      dataIndex: 'baseValue',
      key: 'baseValue',
      render: (value: number | null) => (value !== null ? value : '—'),
    },
    {
      title: `v${data?.targetVersion.versionNo ?? '—'}`,
      dataIndex: 'targetValue',
      key: 'targetValue',
      render: (value: number | null, record: ChainCompareMetricChange) => {
        if (value === null) return '—'
        const changed = record.baseValue !== value
        return (
          <Typography.Text type={changed ? 'warning' : undefined}>
            {value}
          </Typography.Text>
        )
      },
    },
  ]

  return (
    <Drawer
      title="版本对比"
      width={560}
      open={open}
      onClose={onClose}
      destroyOnHidden={false}
    >
      <Space direction="vertical" className="w-full" size={16}>
        <Space>
          <Select
            placeholder="基准版本"
            value={effectiveBase ?? undefined}
            onChange={setBaseId}
            options={versionOptions}
            style={{ minWidth: 220 }}
          />
          <Typography.Text type="secondary">→</Typography.Text>
          <Select
            placeholder="目标版本"
            value={effectiveTarget ?? undefined}
            onChange={setTargetId}
            options={versionOptions}
            style={{ minWidth: 220 }}
          />
        </Space>

        {isLoading && <Spin />}
        {error && (
          <Alert
            type="error"
            message="对比失败"
            description={error instanceof Error ? error.message : '未知错误'}
          />
        )}

        {data && (
          <>
            <div>
              <Typography.Text strong>环节变化</Typography.Text>
              <div className="mt-2">
                <Space wrap size={4}>
                  {data.addedNodes.map((name) => (
                    <Tag key={name} color="success">
                      + {name}
                    </Tag>
                  ))}
                  {data.removedNodes.map((name) => (
                    <Tag key={name} color="error">
                      − {name}
                    </Tag>
                  ))}
                  {data.addedNodes.length === 0 &&
                    data.removedNodes.length === 0 && (
                      <Typography.Text type="secondary">无变化</Typography.Text>
                    )}
                </Space>
              </div>
            </div>

            <div>
              <Typography.Text strong>标的变化</Typography.Text>
              <div className="mt-2">
                <Space wrap size={4}>
                  {data.addedCompanies.map((item) => (
                    <Tag key={item.code} color="success">
                      + {item.name}（{item.nodeName}）
                    </Tag>
                  ))}
                  {data.removedCompanies.map((item) => (
                    <Tag key={item.code} color="error">
                      − {item.name}（{item.nodeName}）
                    </Tag>
                  ))}
                  {data.addedCompanies.length === 0 &&
                    data.removedCompanies.length === 0 && (
                      <Typography.Text type="secondary">无变化</Typography.Text>
                    )}
                </Space>
              </div>
            </div>

            <div>
              <Typography.Text strong>指标变化</Typography.Text>
              <Table
                size="small"
                className="mt-2"
                rowKey={(record) => `${record.nodeName}-${record.field}`}
                columns={metricColumns}
                dataSource={data.metricChanges}
                pagination={false}
                locale={{ emptyText: '无变化' }}
              />
            </div>
          </>
        )}
      </Space>
    </Drawer>
  )
}
