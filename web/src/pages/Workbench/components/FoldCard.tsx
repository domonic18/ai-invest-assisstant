import { MinusOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Card } from 'antd'
import { useState, type ReactNode } from 'react'

interface FoldCardProps {
  title: ReactNode
  extra?: ReactNode
  children: ReactNode
  /** 透传到 Card 根节点的类名（如网格跨列 xl:col-span-2）。 */
  className?: string
  /** 行对齐网格中启用：卡片撑满行高，内容区纵向 flex，支持子元素 mt-auto 吸底。 */
  stretch?: boolean
}

/** 原型规范的折叠卡片：extra 左侧放功能链接，右侧固定折叠按钮。 */
export function FoldCard({ title, extra, children, className, stretch }: FoldCardProps) {
  const [folded, setFolded] = useState(false)

  return (
    <Card
      variant="borderless"
      title={title}
      className={[
        className,
        stretch
          ? 'flex h-full flex-col [&>.ant-card-body]:flex-1 [&>.ant-card-body]:min-h-0'
          : '',
      ]
        .filter(Boolean)
        .join(' ') || undefined}
      extra={
        <span className="inline-flex items-center gap-2">
          {extra}
          <Button
            type="text"
            size="small"
            aria-label={folded ? '展开' : '折叠'}
            icon={folded ? <PlusOutlined /> : <MinusOutlined />}
            onClick={() => setFolded((v) => !v)}
          />
        </span>
      }
    >
      {!folded && stretch ? <div className="flex h-full flex-col">{children}</div> : !folded && children}
    </Card>
  )
}
