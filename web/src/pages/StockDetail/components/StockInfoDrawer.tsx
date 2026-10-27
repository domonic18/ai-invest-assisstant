import { Drawer, Tabs } from 'antd'

import { panelColors } from '@/theme/colors'

import { useStockInfoTabItems } from './useStockInfoTabItems'

interface StockInfoDrawerProps {
  stockCode: string
  open: boolean
  onClose: () => void
}

/** 移动端（<lg）个股信息抽屉：底部上滑，复用桌面右侧面板的四 tab（查询经 react-query 去重）。 */
export function StockInfoDrawer({ stockCode, open, onClose }: StockInfoDrawerProps) {
  const tabItems = useStockInfoTabItems(stockCode)

  return (
    <Drawer
      placement="bottom"
      height="82%"
      open={open}
      onClose={onClose}
      title="个股信息"
      className="stock-detail-drawer"
      styles={{
        body: { padding: 0, display: 'flex', flexDirection: 'column' },
        header: { borderBottom: `1px solid ${panelColors.border}` },
      }}
    >
      <div className="flex-1 overflow-y-auto p-3">
        <Tabs defaultActiveKey="ai" items={tabItems} className="stock-detail-tabs" />
      </div>
    </Drawer>
  )
}
