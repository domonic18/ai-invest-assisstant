import { FileTextOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Empty,
  Input,
  Modal,
  Pagination,
  Select,
  Spin,
  Tag,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import { MarkdownText } from '@/components/common/MarkdownText'
import {
  useResearch,
  useResearchFilters,
  useResearchPdfUrl,
  useSummarizeResearchReport,
} from '@/hooks/useResearch'
import type { ResearchReport } from '@ai-invest/shared'

interface Params {
  q: string
  industry?: string
  broker?: string
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

interface ResearchCardProps {
  report: ResearchReport
  summarizing: boolean
  pdfLoading: boolean
  onShowSummary: () => void
  onOpenPdf: () => void
}

function ResearchCard({
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

export function Research() {
  const [params, setParams] = useState<Params>({ q: '', page: 1, pageSize: 10 })
  const [keyword, setKeyword] = useState('')
  const [industry, setIndustry] = useState<string>()
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [summaryModal, setSummaryModal] = useState<SummaryModal | null>(null)
  const [summarizingId, setSummarizingId] = useState<number | null>(null)
  const [pdfId, setPdfId] = useState<number | null>(null)

  const { data, isLoading, isError, error } = useResearch(params)
  const { data: filters } = useResearchFilters()
  const summarizeMutation = useSummarizeResearchReport()
  const pdfUrlMutation = useResearchPdfUrl()

  const handleSearch = () => {
    const [start, end] = range ?? []
    setParams((prev) => ({
      ...prev,
      q: keyword,
      industry,
      startDate: start ? start.format('YYYY-MM-DD') : undefined,
      endDate: end ? end.format('YYYY-MM-DD') : undefined,
      page: 1,
    }))
  }

  const handleBrokerChange = (broker?: string) => {
    setParams((prev) => ({ ...prev, broker, page: 1 }))
  }

  const handleShowSummary = async (report: ResearchReport) => {
    if (report.hasSummary && report.summary) {
      setSummaryModal({ title: report.title, content: report.summary })
      return
    }
    setSummarizingId(report.id)
    try {
      const result = await summarizeMutation.mutateAsync(report.id)
      setSummaryModal({ title: report.title, content: result.summary })
    } catch (err) {
      message.error(err instanceof Error ? err.message : 'AI 摘要生成失败')
    } finally {
      setSummarizingId(null)
    }
  }

  const handleOpenPdf = async (report: ResearchReport) => {
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
            placeholder="搜索研报标题、公司、行业…"
            allowClear
            className="w-full sm:w-60"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
          />
          <Select
            placeholder="全部行业"
            allowClear
            className="w-full sm:w-40"
            value={industry}
            onChange={(value) => setIndustry(value)}
            options={(filters?.industries ?? []).map((item) => ({
              label: item,
              value: item,
            }))}
          />
          <DatePicker.RangePicker
            className="w-full sm:w-auto"
            value={range}
            onChange={(value) => setRange(value)}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            查询
          </Button>
          <span className="text-xs text-gray-400">共 {data?.total ?? 0} 篇研报</span>
        </div>
      </Card>

      <div>
        <div className="text-xs text-gray-400 mb-2">券商</div>
        <div className="flex flex-wrap gap-2">
          <Tag.CheckableTag checked={!params.broker} onChange={() => handleBrokerChange(undefined)}>
            全部
          </Tag.CheckableTag>
          {(filters?.brokers ?? []).map((broker) => (
            <Tag.CheckableTag
              key={broker}
              checked={params.broker === broker}
              onChange={() => handleBrokerChange(broker)}
            >
              {broker}
            </Tag.CheckableTag>
          ))}
        </div>
      </div>

      {isError && (
        <Card variant="borderless">
          <Empty
            description={error instanceof Error ? error.message : '研报加载失败'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button onClick={() => setParams((prev) => ({ ...prev }))}>重试</Button>
          </Empty>
        </Card>
      )}

      <Spin spinning={isLoading}>
        <div className="space-y-3">
          {data?.items.map((report) => (
            <ResearchCard
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
              <Empty description="暂无研报数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
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
    </div>
  )
}
