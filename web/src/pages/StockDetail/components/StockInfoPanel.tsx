import { DoubleLeftOutlined, DoubleRightOutlined } from '@ant-design/icons'
import { Tabs } from 'antd'

import { panelColors } from '@/theme/colors'

import type { LoadingTask } from '../StockLoadingStatus'
import { StockLoadingStatus } from '../StockLoadingStatus'
import { useStockInfoTabItems } from './useStockInfoTabItems'

interface StockInfoPanelProps {
  stockCode: string
  collapsed: boolean
  tasks: LoadingTask[]
  onExpand: () => void
  onCollapse: () => void
}

/** 桌面端（lg+）右侧信息面板：AI 分析/财务/研报/板块四 tab；移动端走 StockInfoDrawer。 */
export function StockInfoPanel({
  stockCode,
  collapsed,
  tasks,
  onExpand,
  onCollapse,
}: StockInfoPanelProps) {
  const tabItems = useStockInfoTabItems(stockCode)

  return (
    <div
      className="hidden lg:flex lg:flex-col shrink-0 overflow-hidden"
      style={{
        borderLeft: `1px solid ${panelColors.border}`,
        backgroundColor: panelColors.bg,
        width: collapsed ? 36 : 360,
      }}
    >
      {collapsed ? (
        <button
          type="button"
          title="展开信息面板"
          onClick={onExpand}
          className="w-full h-9 flex items-center justify-center text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
        >
          <DoubleLeftOutlined />
        </button>
      ) : (
        <>
          <StockLoadingStatus tasks={tasks} />

          <div className="flex-1 overflow-y-auto p-3">
            <Tabs
              defaultActiveKey="ai"
              items={tabItems}
              className="stock-detail-tabs"
              tabBarExtraContent={{
                right: (
                  <button
                    type="button"
                    title="收起信息面板"
                    onClick={onCollapse}
                    className="flex items-center justify-center w-6 h-6 rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
                  >
                    <DoubleRightOutlined className="!text-[12px]" />
                  </button>
                ),
              }}
            />
          </div>
        </>
      )}
    </div>
  )
}
