import { ReloadOutlined } from '@ant-design/icons'
import { Button, Typography } from 'antd'

interface ErrorStateProps {
  message: string
  onRetry?: () => void
  isRetrying?: boolean
}

export function ErrorState({ message, onRetry, isRetrying }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 py-20">
      <Typography.Text type="danger">{message}</Typography.Text>
      {onRetry && (
        <Button icon={<ReloadOutlined />} onClick={onRetry} loading={isRetrying}>
          重试
        </Button>
      )}
    </div>
  )
}
