import {
  AppstoreOutlined,
  FileTextOutlined,
  RobotOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import type { TabsProps } from 'antd'

import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'
import { useResearch } from '@/hooks/useResearch'
import { useStockDetail, useStockSectors } from '@/hooks/useStocks'
import { useAuthStore } from '@/stores/auth'
import { canAccessFeature, PAGE_SIZE } from '@ai-invest/shared'

import { StockSectors } from '../StockSectors'
import { StockAiAnalysisSection } from './StockAiAnalysisSection'
import { StockFinancial } from './StockFinancial'
import { StockResearch } from './StockResearch'

/**
 * 个股信息四 tab（AI 分析/财务/研报/板块），桌面右栏（StockInfoPanel）与
 * 移动端信息抽屉（StockInfoDrawer）共用；查询经 react-query 缓存去重。
 */
export function useStockInfoTabItems(stockCode: string): TabsProps['items'] {
  const detailQ = useStockDetail(stockCode)
  const sectorsQ = useStockSectors(stockCode)
  const financialQ = useFinancial(stockCode)
  const historyQ = useFinancialHistory(stockCode, 8)
  const user = useAuthStore((s) => s.user)
  const canResearch = canAccessFeature(user, 'research')
  const researchQ = useResearch({ stockCode, pageSize: PAGE_SIZE.inline }, canResearch)

  const stock = detailQ.data

  return [
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
    // 无 research 权限时后端返回 403，整块隐藏避免报错态
    ...(canResearch
      ? [
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
        ]
      : []),
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
}
