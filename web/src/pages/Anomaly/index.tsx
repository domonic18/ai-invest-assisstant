import { Tabs } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'

import { SectorAnomalyPage } from './SectorAnomalyPage'
import { StockAnomalyPage } from './StockAnomalyPage'

/** 异动检测合并页：板块/个股双 tab；tab 切换走路由（/anomaly/sector|stock），
 * page_event 跳转目标路由保持不变，URL 可直达指定 tab。 */
export function AnomalyPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const active = location.pathname.startsWith('/anomaly/stock') ? 'stock' : 'sector'

  return (
    <Tabs
      activeKey={active}
      onChange={(key) => navigate(`/anomaly/${key}`)}
      items={[
        { key: 'sector', label: '板块异动', children: <SectorAnomalyPage /> },
        { key: 'stock', label: '个股异动', children: <StockAnomalyPage /> },
      ]}
    />
  )
}
