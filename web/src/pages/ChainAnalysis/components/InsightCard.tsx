import { Card, Space, Tag, Typography } from 'antd'

export type InsightType = 'opportunity' | 'risk' | 'bottleneck'

interface InsightCardProps {
  type: InsightType
  title: string
  description: string
  level?: 'high' | 'medium' | 'low' | null
  levelLabel?: string
  relatedSegment?: string | null
}

const TYPE_COLORS: Record<InsightType, string> = {
  opportunity: '#10b981',
  risk: '#ef4444',
  bottleneck: '#d29922',
}

function levelColor(level: 'high' | 'medium' | 'low' | null | undefined): string {
  switch (level) {
    case 'high':
      return 'error'
    case 'medium':
      return 'warning'
    case 'low':
      return 'default'
    default:
      return 'default'
  }
}

function levelText(
  level: 'high' | 'medium' | 'low' | null | undefined,
  label: string,
): string {
  if (!level) return ''
  const map: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低',
  }
  return `${map[level]}${label}`
}

export function InsightCard({
  type,
  title,
  description,
  level,
  levelLabel = '置信',
  relatedSegment,
}: InsightCardProps) {
  return (
    <Card
      size="small"
      variant="borderless"
      className="relative overflow-hidden !bg-[#14161c]"
      bodyStyle={{ padding: 12 }}
    >
      <div
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ backgroundColor: TYPE_COLORS[type] }}
      />
      <Space direction="vertical" size={8} className="w-full pl-2">
        <Space wrap size={8}>
          <Typography.Text strong className="text-[#d1d4dc]">
            {title}
          </Typography.Text>
          {level && (
            <Tag color={levelColor(level)}>
              {levelText(level, levelLabel)}
            </Tag>
          )}
          {relatedSegment && <Tag>{relatedSegment}</Tag>}
        </Space>
        <Typography.Paragraph
          type="secondary"
          className="!mb-0 line-clamp-3 text-[#8c8c8c]"
        >
          {description}
        </Typography.Paragraph>
      </Space>
    </Card>
  )
}
