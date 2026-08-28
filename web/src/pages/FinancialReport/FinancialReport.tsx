import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, Empty, Modal, Pagination, Spin, message } from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import { MarkdownText } from '@/components/common/MarkdownText'
import {
  useFinancialReports,
  useFinancialReportPdfUrl,
  useSummarizeFinancialReport,
} from '@/hooks/useFinancialReport'

import { CollectModal } from './CollectModal'
import { FinancialReportCard } from './components/FinancialReportCard'
import { FinancialReportFilters } from './components/FinancialReportFilters'
import {
  type FinancialReportParams,
  type SummaryModal,
} from './utils'

export function FinancialReportPage() {
  const [params, setParams] = useState<FinancialReportParams>({ q: '', page: 1, pageSize: 10 })
  const [keyword, setKeyword] = useState('')
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [summaryModal, setSummaryModal] = useState<SummaryModal | null>(null)
  const [summarizingId, setSummarizingId] = useState<number | null>(null)
  const [pdfId, setPdfId] = useState<number | null>(null)
  const [collectOpen, setCollectOpen] = useState(false)

  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useFinancialReports(params)
  const summarizeMutation = useSummarizeFinancialReport()
  const pdfUrlMutation = useFinancialReportPdfUrl()

  const handleSearch = () => {
    const [start, end] = range ?? []
    setParams((prev) => ({
      ...prev,
      q: keyword,
      startDate: start ? start.format('YYYY-MM-DD') : undefined,
      endDate: end ? end.format('YYYY-MM-DD') : undefined,
      page: 1,
    }))
  }

  const handleReportTypeChange = (reportType?: string) => {
    setParams((prev) => ({ ...prev, reportType, page: 1 }))
  }

  const handleShowSummary = async (reportId: number, title: string | null, hasSummary: boolean, summary?: string | null) => {
    const modalTitle = title ?? '财报摘要'
    if (hasSummary && summary) {
      setSummaryModal({ title: modalTitle, content: summary })
      return
    }
    setSummarizingId(reportId)
    try {
      const result = await summarizeMutation.mutateAsync(reportId)
      setSummaryModal({ title: modalTitle, content: result.summary })
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'AI 摘要生成失败')
    } finally {
      setSummarizingId(null)
    }
  }

  const handleOpenPdf = async (reportId: number) => {
    setPdfId(reportId)
    try {
      const url = await pdfUrlMutation.mutateAsync(reportId)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'PDF 暂不可用')
    } finally {
      setPdfId(null)
    }
  }

  return (
    <div className="space-y-4">
      <FinancialReportFilters
        keyword={keyword}
        range={range}
        reportType={params.reportType}
        total={data?.total ?? 0}
        onKeywordChange={setKeyword}
        onRangeChange={setRange}
        onReportTypeChange={handleReportTypeChange}
        onSearch={handleSearch}
        onCollect={() => setCollectOpen(true)}
      />

      {isError && (
        <Card variant="borderless">
          <Empty
            description={error instanceof Error ? error.message : '财报加载失败'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button onClick={() => setParams((prev) => ({ ...prev }))}>重试</Button>
          </Empty>
        </Card>
      )}

      <Spin spinning={isLoading}>
        <div className="space-y-3">
          {data?.items.map((report) => (
            <FinancialReportCard
              key={report.id}
              report={report}
              summarizing={summarizingId === report.id}
              pdfLoading={pdfId === report.id}
              onShowSummary={() => handleShowSummary(report.id, report.title, report.hasSummary, report.summary)}
              onOpenPdf={() => handleOpenPdf(report.id)}
            />
          ))}
          {!isLoading && (data?.items.length ?? 0) === 0 && (
            <Card variant="borderless">
              <Empty description="暂无财报数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </Card>
          )}
        </div>
      </Spin>

      <div className="flex justify-end">
        <Pagination
          current={data?.page ?? params.page}
          pageSize={data?.pageSize ?? params.pageSize}
          total={data?.total ?? 0}
          showSizeChanger
          onChange={(page, pageSize) =>
            setParams((prev) => ({ ...prev, page, pageSize }))
          }
        />
      </div>

      <Modal
        title={summaryModal?.title}
        open={!!summaryModal}
        onCancel={() => setSummaryModal(null)}
        footer={null}
        width={720}
      >
        {summaryModal && <MarkdownText content={summaryModal.content} />}
      </Modal>

      <CollectModal
        open={collectOpen}
        onClose={() => setCollectOpen(false)}
        onCollected={() =>
          queryClient.invalidateQueries({ queryKey: ['financial-reports'] })
        }
      />
    </div>
  )
}
