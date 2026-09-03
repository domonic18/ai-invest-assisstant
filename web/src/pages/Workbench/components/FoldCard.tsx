import { MinusOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Card } from 'antd'
import { useState, type ReactNode } from 'react'

interface FoldCardProps {
  title: ReactNode
  extra?: ReactNode
  children: ReactNode
}

/** 原型规范的折叠卡片：extra 左侧放功能链接，右侧固定折叠按钮。 */
export function FoldCard({ title, extra, children }: FoldCardProps) {
  const [folded, setFolded] = useState(false)

  return (
    <Card
      variant="borderless"
      title={title}
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
      {!folded && children}
    </Card>
  )
}
