import { FileTextOutlined } from '@ant-design/icons'
import { Button, Card, Tag } from 'antd'
import dayjs from 'dayjs'

import type { ResearchReport } from '@ai-invest/shared'

import { summarySnippet } from '../utils'

interface ResearchCardProps {
  report: ResearchReport
  summarizing: boolean
  pdfLoading: boolean
  onShowSummary: () => void
  onOpenPdf: () => void
}

export function ResearchCard({
  report,
  summarizing,
  pdfLoading,
  onShowSummary,
  onOpenPdf,
}: ResearchCardProps) {
  return (
    <Card variant="outlined" size="small" className="hover:shadow-md transition-shadow">
      <div className="flex gap-4">
        <div className="hidden sm:flex w-[72px] h-[96px] shrink-0 rounded-md bg-gradient-to-br from-indigo-500 to-indigo-700 text-white items-center justify-center text-center text-sm font-bold px-1">
          {report.industry ? (
            <span className="line-clamp-3">{report.industry}</span>
          ) : (
            <FileTextOutlined className="text-2xl" />
          )}
        </div>
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          <div className="text-base font-semibold line-clamp-2" title={report.title}>
            {report.title}
          </div>
          <div className="text-sm text-gray-500 line-clamp-2 leading-relaxed">
            {report.hasSummary && report.summary
              ? summarySnippet(report.summary)
              : report.rating
                ? `评级：${report.rating}${report.industry ? ` · ${report.industry}` : ''}`
                : '尚未生成 AI 摘要'}
          </div>
          <div className="text-xs text-gray-400 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{report.broker ?? '未知券商'}</span>
            <span>·</span>
            <span>
              {report.publishDate ? dayjs(report.publishDate).format('YYYY-MM-DD') : '-'}
            </span>
            {report.pages != null && (
              <>
                <span>·</span>
                <span>{report.pages} 页 PDF</span>
              </>
            )}
            {report.rating && <Tag color="blue">{report.rating}</Tag>}
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
