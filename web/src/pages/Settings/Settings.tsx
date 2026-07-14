import { LogoutOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Space, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

export function Settings() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Typography.Title level={4} className="!mb-0">用户设置</Typography.Title>

      <Card title="基本信息" variant="borderless">
        <Descriptions column={1} bordered>
          <Descriptions.Item label="用户名">{user?.username || '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{user?.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="角色">{user?.isAdmin ? '管理员' : '普通用户'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="账号安全" variant="borderless">
        <Space>
          <Button type="primary" danger icon={<LogoutOutlined />} onClick={handleLogout}>
            退出登录
          </Button>
        </Space>
      </Card>
    </div>
  )
}
