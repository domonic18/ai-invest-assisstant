import {
  BarChartOutlined,
  ContainerOutlined,
  DashboardOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
  ReadOutlined,
  RobotOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Layout, Menu } from 'antd'
import { useLocation, useNavigate, Outlet } from 'react-router-dom'

type MenuItem = NonNullable<MenuProps['items']>[number]

const { Sider, Content } = Layout

const ADMIN_MENU_ITEMS: MenuItem[] = [
  {
    key: '/admin',
    icon: <DashboardOutlined />,
    label: '管理总览',
  },
  {
    key: '/admin/users',
    icon: <TeamOutlined />,
    label: '用户管理',
  },
  {
    key: '/admin/stocks',
    icon: <BarChartOutlined />,
    label: '股票管理',
  },
  {
    key: '/admin/reports',
    icon: <FileTextOutlined />,
    label: '研报管理',
  },
  {
    key: '/admin/news',
    icon: <ReadOutlined />,
    label: '资讯管理',
  },
  {
    key: '/admin/tasks',
    icon: <ContainerOutlined />,
    label: '任务管理',
  },
  {
    key: '/admin/llm-configs',
    icon: <RobotOutlined />,
    label: 'LLM 配置',
  },
  {
    key: '/admin/collector-channels',
    icon: <SettingOutlined />,
    label: '采集渠道',
  },
  {
    key: '/admin/collector',
    icon: <PlayCircleOutlined />,
    label: '采集任务',
  },
]

export function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  const selectedKey =
    ADMIN_MENU_ITEMS.find((item) =>
      item?.key && item.key !== '/admin'
        ? location.pathname.startsWith(String(item.key))
        : false,
    )?.key ?? '/admin'

  return (
    <Layout className="min-h-[calc(100vh-64px)] bg-[#0c0e12]">
      <Sider width={200} className="!bg-[#111318]" theme="dark">
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[String(selectedKey)]}
          items={ADMIN_MENU_ITEMS}
          onClick={({ key }) => navigate(key)}
          className="!bg-transparent border-r-0"
        />
      </Sider>
      <Content className="p-6 overflow-auto">
        <Outlet />
      </Content>
    </Layout>
  )
}
