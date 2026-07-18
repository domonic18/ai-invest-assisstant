import { LogoutOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Space, Switch, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'
import { useColorScheme, useSettingsStore } from '@/stores/settings'

export function Settings() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const colorScheme = useColorScheme()
  const setColorScheme = useSettingsStore((state) => state.setColorScheme)

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

      <Card title="行情配色" variant="borderless">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">红涨绿跌（国内习惯）</div>
            <Typography.Text type="secondary" className="text-xs">
              开启后上涨显示为红色、下跌显示为绿色；关闭则为绿涨红跌（国际习惯）。全站生效。
            </Typography.Text>
          </div>
          <Switch
            checked={colorScheme === 'cn'}
            onChange={(checked) => setColorScheme(checked ? 'cn' : 'us')}
          />
        </div>
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
