import { RobotOutlined, UserOutlined } from '@ant-design/icons'
import { Avatar } from 'antd'

interface MessageAvatarProps {
  role: 'user' | 'assistant'
}

export function MessageAvatar({ role }: MessageAvatarProps) {
  const isAssistant = role === 'assistant'
  return (
    <Avatar
      size={28}
      icon={isAssistant ? <RobotOutlined /> : <UserOutlined />}
      className={`shrink-0 ${
        isAssistant
          ? 'bg-blue-600 text-white'
          : 'bg-gray-600 text-white'
      }`}
    />
  )
}
