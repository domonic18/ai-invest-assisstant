import { CloudDownloadOutlined, FilePdfOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import { App, Button, Empty, Skeleton, Tag } from 'antd'
import { useState } from 'react'

import { fetchFinancialReportPdfUrl } from '@/api/financial_report'
import { useCollectFinancialReport, useFinancialReports } from '@/hooks/useFinancialReports'
import { useAssistantStore } from '@/stores/assistant'

interface StockFinancialReportsProps {
  stockCode: string
  stockName?: string | null
}

/** 个股右栏「财务」tab 底部的财报文件子区：列表 + PDF + AI 解读 + 手动补采。 */
export function StockFinancialReports({ stockCode, stockName }: StockFinancialReportsProps) {
  const { message } = App.useApp()
  const { data, isLoading, isError, refetch } = useFinancialReports(stockCode)
  const collect = useCollectFinancialReport()
  const [pdfLoadingId, setPdfLoadingId] = useState<number | null>(null)

  const openPdf = async (id: number) => {
    setPdfLoadingId(id)
    try {
      const url = await fetchFinancialReportPdfUrl(id)
      if (!url) {
        message.warning('该财报暂无 PDF 文件')
        return
      }
      window.open(url, '_blank', 'noopener')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '获取 PDF 链接失败')
    } finally {
      setPdfLoadingId(null)
    }
  }

  const askSummary = (title: string | null, reportDate: string | null) => {
    useAssistantStore
      .getState()
      .sendQuestion(
        `请解读 ${stockCode}${stockName ? `（${stockName}）` : ''} ${reportDate ?? ''} ${title ?? '财报'}，输出财务要点、同比变化与风险提示`,
      )
  }

  const header = (
    <div className="flex items-center justify-between pt-3 mt-3 border-t border-[#23262d]">
      <span className="text-[13px] font-semibold text-[#f0f1f5]">财报文件</span>
      {data && <span className="text-[11px] text-[#5c616e]">共 {data.total} 份</span>}
    </div>
  )

  const actions = (
    <div className="flex items-center gap-1.5 mt-2">
      <Button
        size="small"
        icon={<CloudDownloadOutlined />}
        loading={collect.isPending}
        onClick={() => collect.mutate(stockCode)}
      >
        补采该股财报
      </Button>
      <Button size="small" icon={<ReloadOutlined />} onClick={() => void refetch()}>
        刷新
      </Button>
    </div>
  )

  if (isLoading) {
    return (
      <div>
        {header}
        <div className="py-2">
          <Skeleton active title={false} paragraph={{ rows: 3 }} />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        {header}
        <div className="py-2 flex items-center gap-2">
          <span className="text-xs text-[#f85149]">财报列表加载失败</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => void refetch()}>
            重试
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div>
      {header}
      {actions}
      {!data?.items.length ? (
        <Empty className="py-4" description="暂无财报文件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="mt-2">
          {data.items.map((item) => (
            <div
              key={item.id}
              className="px-3 py-2.5 mb-2 bg-[#111318] border border-[#23262d] rounded-md transition-colors last:mb-0 hover:border-[rgba(94,106,210,0.25)]"
            >
              <div className="text-[13px] font-semibold leading-snug text-[#f0f1f5] mb-1.5">
                {item.title ?? `${item.reportType ?? '财报'} ${item.reportDate ?? ''}`}
              </div>
              <div className="flex items-center flex-wrap gap-x-2 gap-y-0.5 mb-1.5 text-[11px]">
                {item.reportType && <Tag bordered={false} className="!text-[10px] !leading-4">{item.reportType}</Tag>}
                {item.reportDate && <span className="font-mono text-[#5c616e]">{item.reportDate}</span>}
                {item.hasSummary && !item.summary && (
                  <span className="text-[#5e6ad2]">AI 已解读</span>
                )}
              </div>
              {item.summary && (
                <div className="rounded-md bg-[#181a21] border-l-2 border-[#5e6ad2] px-2.5 py-2 mb-1.5">
                  <div className="flex items-center gap-1 text-[10px] font-semibold text-[#5e6ad2] mb-1">
                    <RobotOutlined style={{ fontSize: 11 }} />
                    AI 解读要点
                  </div>
                  <p className="m-0 text-xs text-[#8a8f98] leading-[1.6] line-clamp-4">
                    {item.summary}
                  </p>
                </div>
              )}
              <div className="flex items-center gap-1">
                <Button
                  size="small"
                  type="text"
                  className="!px-1 !text-[11px] !h-6"
                  icon={<FilePdfOutlined />}
                  loading={pdfLoadingId === item.id}
                  onClick={() => void openPdf(item.id)}
                >
                  PDF
                </Button>
                <Button
                  size="small"
                  type="text"
                  className="!px-1 !text-[11px] !h-6"
                  icon={<RobotOutlined />}
                  onClick={() => askSummary(item.title, item.reportDate)}
                >
                  AI 解读
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
