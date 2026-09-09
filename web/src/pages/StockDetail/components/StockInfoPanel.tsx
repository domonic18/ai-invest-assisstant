import {
  AppstoreOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  FileTextOutlined,
  RobotOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { Tabs } from 'antd'

import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'
import { useResearch } from '@/hooks/useResearch'
import { useStockDetail, useStockSectors } from '@/hooks/useStocks'
import { panelColors } from '@/theme/colors'
import { PAGE_SIZE, type Stock } from '@ai-invest/shared'

import { StockLoadingStatus, type LoadingTask } from '../StockLoadingStatus'
import { StockSectors } from '../StockSectors'
import { StockAiAnalysisSection } from './StockAiAnalysisSection'
import { StockFinancial } from './StockFinancial'
import { StockResearch } from './StockResearch'

interface StockInfoPanelProps {
  stockCode: string
  collapsed: boolean
  tasks: LoadingTask[]
  onExpand: () => void
  onCollapse: () => void
}

export function StockInfoPanel({
  stockCode,
  collapsed,
  tasks,
  onExpand,
  onCollapse,
}: StockInfoPanelProps) {
  const detailQ = useStockDetail(stockCode)
  const sectorsQ = useStockSectors(stockCode)
  const financialQ = useFinancial(stockCode)
  const historyQ = useFinancialHistory(stockCode, 8)
  const researchQ = useResearch({ stockCode, pageSize: PAGE_SIZE.inline })

  const stock: Stock | undefined = detailQ.data

  const tabItems = [
    {
      key: 'ai',
      label: (
        <span className="text-xs">
          <RobotOutlined className="mr-1" />
          AI 分析
        </span>
      ),
      children: <StockAiAnalysisSection stockCode={stockCode} />,
    },
    {
      key: 'financial',
      label: (
        <span className="text-xs">
          <WalletOutlined className="mr-1" />
          财务
        </span>
      ),
      children: (
        <StockFinancial
          stockCode={stockCode}
          stockName={stock?.name}
          data={financialQ.data}
          history={historyQ.data}
          isLoading={financialQ.isLoading}
          historyLoading={historyQ.isLoading}
          isError={financialQ.isError}
          historyError={historyQ.isError}
          onRetry={() => {
            financialQ.refetch()
            historyQ.refetch()
          }}
        />
      ),
    },
    {
      key: 'research',
      label: (
        <span className="text-xs">
          <FileTextOutlined className="mr-1" />
          研报
        </span>
      ),
      children: (
        <StockResearch
          stockCode={stockCode}
          data={researchQ.data}
          isLoading={researchQ.isLoading}
          isError={researchQ.isError}
          onRetry={() => researchQ.refetch()}
        />
      ),
    },
    {
      key: 'sector',
      label: (
        <span className="text-xs">
          <AppstoreOutlined className="mr-1" />
          板块
        </span>
      ),
      children: (
        <StockSectors
          sectors={sectorsQ.data}
          stock={stock}
          isLoading={sectorsQ.isLoading}
          isError={sectorsQ.isError}
          onRetry={() => sectorsQ.refetch()}
        />
      ),
    },
  ]

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
