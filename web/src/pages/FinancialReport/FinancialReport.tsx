import { FileTextOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Empty,
  Input,
  Modal,
  Pagination,
  Spin,
  Tag,
  message,
} from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import { MarkdownText } from '@/components/common/MarkdownText'
import {
  useFinancialReports,
  useFinancialReportPdfUrl,
  useSummarizeFinancialReport,
} from '@/hooks/useFinancialReport'
import type { FinancialReport } from '@ai-invest/shared'

import { CollectModal } from './CollectModal'

const REPORT_TYPE_OPTIONS = [
  { value: 'annual', label: '年报' },
  { value: 'semi_annual', label: '半年报' },
  { value: 'q1', label: '一季报' },
  { value: 'q3', label: '三季报' },
]

const REPORT_TYPE_LABELS = new Map(
  REPORT_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

interface Params {
  q: string
  reportType?: string
  startDate?: string
  endDate?: string
  page: number
  pageSize: number
}

interface SummaryModal {
  title: string
  content: string
}

function summarySnippet(summary: string): string {
  return summary
    .replace(/[#*`>-]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function formatFileSize(size: number | null): string | null {
  if (size == null) return null
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${size} B`
}

interface FinancialReportCardProps {
  report: FinancialReport
  summarizing: boolean
  pdfLoading: boolean
  onShowSummary: () => void
  onOpenPdf: () => void
}

function FinancialReportCard({
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

export function FinancialReportPage() {
  const [params, setParams] = useState<Params>({ q: '', page: 1, pageSize: 10 })
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

  const handleShowSummary = async (report: FinancialReport) => {
    const title = report.title ?? '财报摘要'
    if (report.hasSummary && report.summary) {
      setSummaryModal({ title, content: report.summary })
      return
    }
    setSummarizingId(report.id)
    try {
      const result = await summarizeMutation.mutateAsync(report.id)
      setSummaryModal({ title, content: result.summary })
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'AI 摘要生成失败')
    } finally {
      setSummarizingId(null)
    }
  }

  const handleOpenPdf = async (report: FinancialReport) => {
    setPdfId(report.id)
    try {
      const url = await pdfUrlMutation.mutateAsync(report.id)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'PDF 暂不可用')
    } finally {
      setPdfId(null)
    }
  }

  return (
    <div className="space-y-4">
      <Card variant="borderless" size="small">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="搜索财报标题、股票名称或代码…"
            allowClear
            className="w-full sm:w-60"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
          />
          <DatePicker.RangePicker
            className="w-full sm:w-auto"
            value={range}
            onChange={(value) => setRange(value)}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            查询
          </Button>
          <span className="text-xs text-gray-400">共 {data?.total ?? 0} 份财报</span>
          <div className="flex-1" />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCollectOpen(true)}
          >
            采集财报
          </Button>
        </div>
      </Card>

      <div>
        <div className="text-xs text-gray-400 mb-2">报告类型</div>
        <div className="flex flex-wrap gap-2">
          <Tag.CheckableTag
            checked={!params.reportType}
            onChange={() => handleReportTypeChange(undefined)}
          >
            全部
          </Tag.CheckableTag>
          {REPORT_TYPE_OPTIONS.map((option) => (
            <Tag.CheckableTag
              key={option.value}
              checked={params.reportType === option.value}
              onChange={() => handleReportTypeChange(option.value)}
            >
              {option.label}
            </Tag.CheckableTag>
          ))}
        </div>
      </div>

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
              onShowSummary={() => handleShowSummary(report)}
              onOpenPdf={() => handleOpenPdf(report)}
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
