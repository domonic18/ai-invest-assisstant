import { Card, Progress, Table, Tag, Typography } from 'antd'
import { USAGE_FEATURE_LABELS, type UsageFeature } from '@ai-invest/shared'

import { useMyQuota, useMyUsage } from '@/hooks/useAccount'
import { formatDateTime } from '@/utils/formatters'

function formatTokens(value: number | null, unlimitedLabel = '不限') {
  if (value == null) return unlimitedLabel
  return value.toLocaleString('zh-CN')
}

export function QuotaSection() {
  const quotaQ = useMyQuota()
  const usageQ = useMyUsage()

  const quota = quotaQ.data
  const usage = usageQ.data
  const percent =
    quota && quota.totalTokens && quota.totalTokens > 0
      ? Math.min(100, Math.round((quota.usedTokens / quota.totalTokens) * 100))
      : 0
  const nearExhausted =
    quota != null &&
    !quota.unlimited &&
    quota.remainingTokens != null &&
    quota.totalTokens != null &&
    quota.remainingTokens < quota.totalTokens * 0.1

  return (
    <Card
      variant="borderless"
      title="AI 配额与用量"
      extra={
        quota?.unlimited ? (
          <Tag bordered={false} color="purple">不限额</Tag>
        ) : null
      }
    >
      {quotaQ.isLoading || !quota ? (
        <Typography.Text type="secondary" className="text-sm">
          加载中…
        </Typography.Text>
      ) : (
        <>
          <div className="flex items-center gap-6 flex-wrap">
            <Progress
              type="circle"
              size={96}
              percent={quota.unlimited ? 100 : percent}
              strokeColor={
                quota.unlimited ? '#9d7ff5' : nearExhausted ? '#f87171' : '#5e6ad2'
              }
              format={() =>
                quota.unlimited ? '不限' : `${percent}%`
              }
            />
            <div className="text-xs space-y-1">
              <div className="text-[#8a8f98]">
                一次性总量：
                <span className="font-mono text-[#f0f1f5]">
                  {formatTokens(quota.totalTokens)}
                </span>{' '}
                tokens
              </div>
              <div className="text-[#8a8f98]">
                已消耗（系统模型）：
                <span className="font-mono text-[#f0f1f5]">
                  {formatTokens(quota.usedTokens)}
                </span>{' '}
                tokens
              </div>
              <div className="text-[#8a8f98]">
                剩余：
                <span
                  className={`font-mono ${
                    nearExhausted ? 'text-[#f87171]' : 'text-[#f0f1f5]'
                  }`}
                >
                  {formatTokens(quota.remainingTokens)}
                </span>{' '}
                tokens
              </div>
              {quota.byokEnabled && (
                <div className="text-[#8a8f98]">
                  自备模型：<Tag bordered={false} color="green" className="!mr-0">已启用</Tag>
                  <span className="text-[#5c616e]">（当前 AI 调用不占配额）</span>
                </div>
              )}
            </div>
          </div>

          {nearExhausted && (
            <div className="mt-3 rounded-md border border-[rgba(248,113,113,0.3)] bg-[rgba(248,113,113,0.06)] px-3 py-2 text-xs text-[#f87171]">
              配额即将耗尽：可在下方「我的模型」配置自有 API Key，或联系管理员追加配额。
            </div>
          )}

          {usage && Object.keys(usage.byFeature).length > 0 && (
            <div className="mt-4">
              <Typography.Text type="secondary" className="text-xs">
                按功能消耗
              </Typography.Text>
              <div className="mt-2 space-y-1.5">
                {Object.entries(usage.byFeature).map(([feature, tokens]) => (
                  <div key={feature} className="flex items-center gap-3 text-xs">
                    <span className="w-24 text-[#8a8f98]">
                      {USAGE_FEATURE_LABELS[feature as UsageFeature] ?? feature}
                    </span>
                    <div className="flex-1 h-1.5 rounded bg-[#181a21] overflow-hidden">
                      <div
                        className="h-full rounded bg-[#5e6ad2]"
                        style={{
                          width: `${Math.min(
                            100,
                            (tokens / Math.max(1, quota.usedTokens)) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                    <span className="font-mono text-[#8a8f98] w-24 text-right">
                      {tokens.toLocaleString('zh-CN')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {usage && usage.items.length > 0 && (
            <div className="mt-4">
              <Typography.Text type="secondary" className="text-xs">
                最近消耗明细
              </Typography.Text>
              <Table
                className="mt-2"
                size="small"
                rowKey={(row) => row.createdAt + row.modelName}
                dataSource={usage.items.slice(0, 20)}
                pagination={false}
                columns={[
                  {
                    title: '时间',
                    dataIndex: 'createdAt',
                    width: 150,
                    render: (value: string) => (
                      <span className="text-xs">{formatDateTime(value)}</span>
                    ),
                  },
                  {
                    title: '功能',
                    dataIndex: 'feature',
                    width: 100,
                    render: (value: UsageFeature) => (
                      <span className="text-xs">
                        {USAGE_FEATURE_LABELS[value] ?? value}
                      </span>
                    ),
                  },
                  {
                    title: '模型',
                    dataIndex: 'modelName',
                    ellipsis: true,
                    render: (value: string, row) => (
                      <span className="text-xs">
                        {value}
                        {row.outlet === 'byok' && (
                          <Tag bordered={false} color="green" className="!ml-1">
                            自有
                          </Tag>
                        )}
                      </span>
                    ),
                  },
                  {
                    title: 'Tokens',
                    dataIndex: 'totalTokens',
                    width: 110,
                    align: 'right',
                    render: (value: number, row) => (
                      <span className="font-mono text-xs">
                        {value.toLocaleString('zh-CN')}
                        {row.estimated && (
                          <span className="text-[#5c616e] ml-1" title="无协议 usage，按字符估算">
                            ~
                          </span>
                        )}
                      </span>
                    ),
                  },
                ]}
              />
            </div>
          )}
        </>
      )}
    </Card>
  )
}
