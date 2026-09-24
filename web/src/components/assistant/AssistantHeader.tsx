import { CloseOutlined, MenuOutlined, MoreOutlined, RobotOutlined } from '@ant-design/icons'
import { Avatar, Button, Typography } from 'antd'

interface AssistantHeaderProps {
  title?: string | null
  onClose: () => void
  /** 窄屏（移动端）下显示会话列表切换按钮：单栏布局中会话列表收进浮层 */
  showSessionsToggle?: boolean
  sessionsOpen?: boolean
  onToggleSessions?: () => void
}

export function AssistantHeader({
  title,
  onClose,
  showSessionsToggle = false,
  sessionsOpen = false,
  onToggleSessions,
}: AssistantHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        {showSessionsToggle && (
          <Button
            type="text"
            size="small"
            aria-label={sessionsOpen ? '收起会话列表' : '打开会话列表'}
            icon={<MenuOutlined />}
            onClick={onToggleSessions}
            className={sessionsOpen ? 'text-blue-400' : 'text-gray-400 hover:text-white'}
          />
        )}
        <Avatar size={32} icon={<RobotOutlined />} className="bg-blue-600 text-white" />
        <div className="min-w-0">
          <Typography.Text className="block text-sm font-medium text-white">
            AI 投研助手
          </Typography.Text>
          {title ? (
            <Typography.Text ellipsis className="block max-w-[240px] text-xs text-gray-400">
              {title}
            </Typography.Text>
          ) : (
            <span className="text-xs text-gray-500">新会话</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <Button
          type="text"
          size="small"
          icon={<MoreOutlined />}
          className="text-gray-400 hover:text-white"
        />
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={onClose}
          className="text-gray-400 hover:text-white"
        />
      </div>
    </div>
  )
}
