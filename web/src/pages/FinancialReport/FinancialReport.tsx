import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, Empty, Pagination, Spin, Table, Tag, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import type { FinancialReport } from '@ai-invest/shared'

import { MarkdownText } from '@/components/common/MarkdownText'
import {
  useFinancialReports,
  useFinancialReportPdfUrl,
  useSummarizeFinancialReport,
} from '@/hooks/useFinancialReport'

import { CollectModal } from './CollectModal'
import { FinancialReportFilters } from './components/FinancialReportFilters'
import {
  type FinancialReportParams,
  type SummaryPanel,
  formatFileSize,
  REPORT_TYPE_LABELS,
  REPORT_TYPE_TAG_COLORS,
} from './utils'

function periodLabel(report: FinancialReport): string {
  const type = report.reportType
    ? (REPORT_TYPE_LABELS.get(report.reportType) ?? report.reportType)
    : null
  const year = report.reportDate ? `${report.reportDate.slice(0, 4)} ` : ''
  return type ? `${year}${type}` : (report.reportDate?.slice(0, 4) ?? '-')
}

export function FinancialReportPage() {
  const [params, setParams] = useState<FinancialReportParams>({ q: '', page: 1, pageSize: 10 })
  const [keyword, setKeyword] = useState('')
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [summaryPanel, setSummaryPanel] = useState<SummaryPanel | null>(null)
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

  /** 生成（或从库内直接展示）摘要，并以行内展开面板呈现。 */
  const handleShowSummary = async (report: FinancialReport) => {
    const title = `AI 摘要 · ${report.stockName ?? ''}${
      report.stockCode ? ` ${report.stockCode}` : ''
    } · ${periodLabel(report)}`
    if (report.hasSummary && report.summary) {
      setSummaryPanel({ reportId: report.id, title, content: report.summary, cached: true })
      return
    }
    setSummarizingId(report.id)
    try {
      const result = await summarizeMutation.mutateAsync(report.id)
      setSummaryPanel({
        reportId: report.id,
        title,
        content: result.summary,
        cached: result.cached,
      })
      queryClient.invalidateQueries({ queryKey: ['financial-reports'] })
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

  const columns: ColumnsType<FinancialReport> = [
    {
      title: '股票',
      key: 'stock',
      width: 170,
      render: (_, report) =>
        report.stockCode ? (
          <span>
            {report.stockName ?? report.stockCode}
            <span className="ml-1.5 text-[11px] text-gray-400 font-mono">{report.stockCode}</span>
          </span>
        ) : (
          (report.title ?? '-')
        ),
    },
    { title: '报告期', key: 'period', width: 110, render: (_, report) => periodLabel(report) },
    {
      title: '类型',
      dataIndex: 'reportType',
      width: 90,
      render: (value: string | null) => {
        if (!value) return '-'
        const label = REPORT_TYPE_LABELS.get(value) ?? value
        return <Tag color={REPORT_TYPE_TAG_COLORS[value] ?? 'default'}>{label}</Tag>
      },
    },
    {
      title: '发布日期',
      dataIndex: 'reportDate',
      width: 110,
      render: (value: string | null) => (value ? value.slice(0, 10) : '-'),
    },
    {
      title: '文件',
      dataIndex: 'fileSize',
      width: 80,
      render: (value: number | null) => formatFileSize(value) ?? '-',
    },
    {
      title: 'AI 摘要',
      key: 'summary',
      width: 110,
      render: (_, report) => {
        if (summarizingId === report.id) return <Tag color="amber">AI 生成中…</Tag>
        return report.hasSummary ? (
          <Tag color="green">已生成</Tag>
        ) : (
          <Tag>未生成</Tag>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, report) => (
        <div className="flex gap-1.5 whitespace-nowrap">
          {report.hasSummary ? (
            <Button size="small" type="link" className="!px-0" onClick={() => handleShowSummary(report)}>
              查看摘要
            </Button>
          ) : (
            <Button
              size="small"
              type="link"
              className="!px-0"
              loading={summarizingId === report.id}
              onClick={() => handleShowSummary(report)}
            >
              AI 摘要
            </Button>
          )}
          <Button
            size="small"
            type="link"
            className="!px-0"
            loading={pdfId === report.id}
            onClick={() => handleOpenPdf(report.id)}
          >
            PDF
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <FinancialReportFilters
        keyword={keyword}
        range={range}
        reportType={params.reportType}
        onKeywordChange={setKeyword}
        onRangeChange={setRange}
        onReportTypeChange={handleReportTypeChange}
        onSearch={handleSearch}
        onCollect={() => setCollectOpen(true)}
      />

      {isError ? (
        <Card variant="borderless">
          <Empty
            description={error instanceof Error ? error.message : '财报加载失败'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button onClick={() => setParams((prev) => ({ ...prev }))}>重试</Button>
          </Empty>
        </Card>
      ) : (
        <Card
          variant="borderless"
          title="财报列表"
          extra={<span className="text-xs text-gray-400">共 {data?.total ?? 0} 份</span>}
        >
          <Spin spinning={isLoading}>
            <Table<FinancialReport>
              rowKey="id"
              columns={columns}
              dataSource={data?.items ?? []}
              size="small"
              scroll={{ x: 860 }}
              expandable={{
                expandedRowKeys: summaryPanel ? [summaryPanel.reportId] : [],
                onExpandedRowsChange: (keys) => {
                  if (!keys.includes(summaryPanel?.reportId ?? -1)) setSummaryPanel(null)
                },
                expandedRowRender: (report) =>
                  summaryPanel && summaryPanel.reportId === report.id ? (
                    <div className="rounded-lg border border-gray-800 bg-[#181a21] p-4">
                      <div className="flex items-center justify-between mb-2.5">
                        <h4 className="text-[13px] font-semibold">{summaryPanel.title}</h4>
                        <div className="flex items-center gap-2">
                          {summaryPanel.cached === true && <Tag color="green">命中缓存</Tag>}
                          {summaryPanel.cached === false && <Tag color="blue">本次新生成</Tag>}
                          <Button size="small" type="text" onClick={() => setSummaryPanel(null)}>
                            收起
                          </Button>
                        </div>
                      </div>
                      <MarkdownText content={summaryPanel.content} />
                    </div>
                  ) : null,
              }}
              locale={{ emptyText: <Empty description="暂无财报数据" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              pagination={false}
            />
          </Spin>
          <div className="mt-3 text-[10px] text-gray-500 pt-2.5 border-t border-dashed border-gray-800">
            AI 摘要按输入幂等缓存：同报告期重复点击不再调用 LLM。摘要仅作辅助阅读，不构成投资建议。
          </div>
        </Card>
      )}

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
