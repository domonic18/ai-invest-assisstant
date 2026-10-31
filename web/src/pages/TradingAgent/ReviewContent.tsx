/** 复盘正文展示（指标卡 / 分层结论 / 分区 / 方法论验证 / 逐笔判定 / 经验）。 */

import { Descriptions, Space, Table, Tag, Typography } from 'antd'

import type {
  ApiTradingAgentMethodologyCheck,
  ApiTradingAgentReview,
  ApiTradingAgentReviewExperience,
  ApiTradingAgentTradeVerdict,
} from '@ai-invest/shared'

import { ReviewMetricsGrid } from './ReviewMetricsGrid'

const VERDICT_ITEMS: Record<string, { label: string; color: string }> = {
  correct: { label: '对', color: 'success' },
  wrong: { label: '错', color: 'error' },
  neutral: { label: '中性', color: 'default' },
}

const MEM_TYPE_LABELS: Record<ApiTradingAgentReviewExperience['memType'], string> = {
  discipline: '纪律',
  method: '方法',
  lesson: '教训',
}

const CHECK_VERDICT_ITEMS: Record<
  ApiTradingAgentMethodologyCheck['verdict'],
  { label: string; color: string }
> = {
  followed: { label: '遵守', color: 'success' },
  violated: { label: '违反', color: 'error' },
  not_applicable: { label: '不适用', color: 'default' },
}

function VerdictTag({ value }: { value: string }) {
  const item = VERDICT_ITEMS[value] ?? VERDICT_ITEMS.neutral
  return <Tag color={item.color}>{item.label}</Tag>
}

const verdictColumns = [
  { title: '代码', dataIndex: 'stockCode', width: 80 },
  {
    title: '选股',
    dataIndex: 'selectionVerdict',
    width: 64,
    render: (v: string) => <VerdictTag value={v} />,
  },
  {
    title: '计划',
    dataIndex: 'planVerdict',
    width: 64,
    render: (v: string) => <VerdictTag value={v} />,
  },
  {
    title: '执行',
    dataIndex: 'executionVerdict',
    width: 64,
    render: (v: string) => <VerdictTag value={v} />,
  },
  { title: '归因', dataIndex: 'reason', ellipsis: true },
]

/** 已执行但空仓无复盘对象：与「未生成」区分。 */
function NoTargetNotice({ review }: { review: ApiTradingAgentReview }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-3">
      <div className="flex items-center gap-2">
        <Tag color="gold" className="!mr-0">
          已执行 · 无复盘对象
        </Tag>
        <span className="text-xs text-white/40">{review.tradeDate}</span>
      </div>
      <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-xs whitespace-pre-wrap">
        {review.noTargetReason}
      </Typography.Paragraph>
    </div>
  )
}

export function ReviewContent({ review }: { review: ApiTradingAgentReview }) {
  if (review.noTargetReason) return <NoTargetNotice review={review} />

  return (
    <Space direction="vertical" size="small" className="w-full">
      {review.metrics && <ReviewMetricsGrid metrics={review.metrics} />}

      <Descriptions size="small" column={1}>
        <Descriptions.Item label="基准日">{review.tradeDate}</Descriptions.Item>
        <Descriptions.Item label="整体">
          <Typography.Text>{review.overall}</Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="盘面语境">
          {review.marketContext || <span className="text-white/40">无</span>}
        </Descriptions.Item>
        <Descriptions.Item label="偏差">{review.bias}</Descriptions.Item>
        <Descriptions.Item label="建议">{review.suggestion}</Descriptions.Item>
      </Descriptions>

      {review.sections.length > 0 && (
        <div className="space-y-2">
          {review.sections.map((section) => (
            <div
              key={section.key}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2"
            >
              <Typography.Text strong className="text-xs">
                {section.title}
              </Typography.Text>
              <Typography.Paragraph
                className="!mb-0 mt-1 text-xs whitespace-pre-wrap"
                type="secondary"
              >
                {section.body}
              </Typography.Paragraph>
            </div>
          ))}
        </div>
      )}

      {review.methodologyCheck.length > 0 && (
        <div>
          <Typography.Text type="secondary" className="text-xs">
            方法论验证
          </Typography.Text>
          <ul className="mt-1 space-y-1 pl-4">
            {review.methodologyCheck.map((check) => {
              const verdict = CHECK_VERDICT_ITEMS[check.verdict] ?? {
                label: check.verdict,
                color: 'default',
              }
              return (
                <li key={check.title}>
                  <Tag color={verdict.color}>{verdict.label}</Tag>
                  <Typography.Text strong className="text-xs">
                    {check.title}
                  </Typography.Text>
                  <Typography.Paragraph className="mb-0 text-xs" type="secondary">
                    {check.note}
                  </Typography.Paragraph>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {review.trades.length > 0 && (
        <Table<ApiTradingAgentTradeVerdict>
          size="small"
          rowKey="clOrdId"
          columns={verdictColumns}
          dataSource={review.trades}
          pagination={false}
          scroll={{ x: 520 }}
        />
      )}

      {review.experiences.length > 0 && (
        <div>
          <Typography.Text type="secondary" className="text-xs">
            提取经验
          </Typography.Text>
          <ul className="mt-1 space-y-1 pl-4">
            {review.experiences.map((exp) => (
              <li key={exp.title}>
                <Tag>{MEM_TYPE_LABELS[exp.memType] ?? exp.memType}</Tag>
                <Typography.Text strong className="text-xs">
                  {exp.title}
                </Typography.Text>
                <Typography.Paragraph className="mb-0 text-xs" type="secondary">
                  {exp.body}
                </Typography.Paragraph>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Space>
  )
}
