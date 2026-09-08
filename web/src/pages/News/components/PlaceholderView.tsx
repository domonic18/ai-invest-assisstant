import { Card, Empty } from 'antd'

interface PlaceholderViewProps {
  title: string
  description: string
}

/** 迭代 4 视图占位（重点与跟踪 / 热点主题），数据链路未上线不模拟内容。 */
export function PlaceholderView({ title, description }: PlaceholderViewProps) {
  return (
    <Card variant="borderless">
      <Empty
        description={
          <span>
            {title}
            <span className="block text-xs opacity-50 mt-1">{description}</span>
          </span>
        }
      />
    </Card>
  )
}
