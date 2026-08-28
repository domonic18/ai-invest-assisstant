import { ReloadOutlined } from '@ant-design/icons'
import { Button, Empty, Skeleton, Spin, Typography } from 'antd'

import { FinancialTrendCharts } from '@/components/charts/FinancialTrendCharts'
import { FINANCIAL_METRIC_LABELS } from '@/constants/financial'
import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'

interface StockFinancialProps {
  data: ReturnType<typeof useFinancial>['data']
  history: ReturnType<typeof useFinancialHistory>['data']
  isLoading: boolean
  historyLoading: boolean
  isError: boolean
  historyError: boolean
  onRetry: () => void
}

export function StockFinancial({
  data,
  history,
  isLoading,
  historyLoading,
  isError,
  historyError,
  onRetry,
}: StockFinancialProps) {
  if (isLoading) {
    return (
      <div className="py-2">
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="py-4 flex flex-col items-start gap-2">
        <Typography.Text type="danger" className="text-xs">
          财务数据加载失败
        </Typography.Text>
        <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
          重试
        </Button>
      </div>
    )
  }

  if (!data) {
    return <Empty description="暂无财务数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  const renderPercent = (value: number | null) =>
    value === null ? '-' : `${(value * 100).toFixed(2)}%`

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-[#8c8c8c]">
        <span>报告期：{data.reportDate || '-'}</span>
        <span>类型：{data.reportType || '-'}</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {Object.entries(data.metrics).map(([key, value]) => (
          <div
            key={key}
            className="flex flex-col p-2 rounded"
            style={{ backgroundColor: '#14161c' }}
          >
            <span className="text-[10px] text-[#8c8c8c]">{FINANCIAL_METRIC_LABELS[key] || key}</span>
            <span className="text-sm text-[#d1d4dc] font-medium">{renderPercent(value)}</span>
          </div>
        ))}
      </div>

      {historyError ? (
        <div className="flex items-center gap-2">
          <Typography.Text type="danger" className="text-xs">
            历史趋势加载失败
          </Typography.Text>
          <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
            重试
          </Button>
        </div>
      ) : historyLoading ? (
        <div className="flex justify-center py-6">
          <Spin size="small" />
        </div>
      ) : history?.history.length ? (
        <FinancialTrendCharts history={history.history} />
      ) : (
        <Empty description="暂无历史财务趋势" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </div>
  )
}
