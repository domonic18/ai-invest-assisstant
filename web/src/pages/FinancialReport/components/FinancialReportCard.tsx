import { FileTextOutlined } from '@ant-design/icons'
import { Button, Card, Tag } from 'antd'
import dayjs from 'dayjs'

import type { FinancialReport } from '@ai-invest/shared'

import { formatFileSize, REPORT_TYPE_LABELS, summarySnippet } from '../utils'

interface FinancialReportCardProps {
  report: FinancialReport
  summarizing: boolean
  pdfLoading: boolean
  onShowSummary: () => void
  onOpenPdf: () => void
}

export function FinancialReportCard({
  report,
  summarizing,
  pdfLoading,
  onShowSummary,
  onOpenPdf,
}: FinancialReportCardProps) {
  const typeLabel = report.reportType
    ? (REPORT_TYPE_LABELS.get(report.reportType) ?? report.reportType)
    : null
  const year = report.reportDate ? dayjs(report.reportDate).format('YYYY') : null
  const fileSize = formatFileSize(report.fileSize)
  const title = report.title ?? '未命名财报'

  return (
    <Card variant="outlined" size="small" className="hover:shadow-md transition-shadow">
      <div className="flex gap-4">
        <div className="hidden sm:flex w-[72px] h-[96px] shrink-0 rounded-md bg-gradient-to-br from-emerald-500 to-emerald-700 text-white flex-col items-center justify-center text-center px-1">
          {typeLabel ? (
            <>
              <span className="text-sm font-bold">{typeLabel}</span>
              {year && <span className="text-xs mt-1">{year}</span>}
            </>
          ) : (
            <FileTextOutlined className="text-2xl" />
          )}
        </div>
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          {report.stockCode && (
            <div className="text-sm font-medium text-gray-700">
              {report.stockName ? `${report.stockName}（${report.stockCode}）` : report.stockCode}
            </div>
          )}
          <div className="text-base font-semibold line-clamp-2" title={title}>
            {title}
          </div>
          <div className="text-sm text-gray-500 line-clamp-2 leading-relaxed">
            {report.hasSummary && report.summary
              ? summarySnippet(report.summary)
              : report.stockName
                ? `${report.stockName} · 尚未生成 AI 摘要`
                : '尚未生成 AI 摘要'}
          </div>
          <div className="text-xs text-gray-400 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>
              {report.reportDate ? dayjs(report.reportDate).format('YYYY-MM-DD') : '-'}
            </span>
            {fileSize && <span>{fileSize}</span>}
            {typeLabel && <Tag color="blue">{typeLabel}</Tag>}
            {report.hasSummary && <Tag color="green">AI 摘要已生成</Tag>}
          </div>
          <div className="flex flex-wrap gap-2 mt-1">
            <Button size="small" type="primary" ghost loading={summarizing} onClick={onShowSummary}>
              AI 摘要
            </Button>
            <Button size="small" loading={pdfLoading} onClick={onOpenPdf}>
              在线阅读
            </Button>
            <Button size="small" loading={pdfLoading} onClick={onOpenPdf}>
              下载 PDF
            </Button>
          </div>
        </div>
      </div>
    </Card>
  )
}
