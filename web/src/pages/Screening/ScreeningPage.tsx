import { ThunderboltOutlined } from '@ant-design/icons'
import { Alert, Button, Empty, message, Space, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'

import { queryScreening } from '@/api/screening'
import { useStockScreeningEvent } from '@/pages/Screening/useStockScreening'
import type { StockScreeningRow } from '@/stores/assistant'
import { useScreeningStore } from '@/stores/screening'
import { useColorScheme } from '@/stores/settings'
import { apiErrorMessage } from '@/utils/errorMessage'

import { AddToWatchlistModal } from './AddToWatchlistModal'
import { buildScreeningColumns } from './columns'
import { ScreeningSearchBox } from './ScreeningSearchBox'
import { useScreeningHistory } from './useScreeningHistory'

export function ScreeningPage() {
  useColorScheme()
  useStockScreeningEvent()
  const result = useScreeningStore((s) => s.result)
  const setResult = useScreeningStore((s) => s.setResult)
  const { history, add, clear } = useScreeningHistory()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [modalOpen, setModalOpen] = useState(false)

  const dataSource = useMemo(() => result?.stocks ?? [], [result])
  const tableColumns: ColumnsType<StockScreeningRow> = useMemo(
    () => [
      {
        title: '序号',
        key: 'index',
        width: 64,
        fixed: 'left',
        render: (_: unknown, __: StockScreeningRow, index: number) => index + 1,
      },
      ...(result ? buildScreeningColumns(result.columns) : []),
    ],
    [result],
  )
  const selectedRows = useMemo(
    () => dataSource.filter((row) => selectedCodes.has(row.stockCode)),
    [dataSource, selectedCodes],
  )

  const runSearch = async (text: string) => {
    if (loading) return
    setQuery(text)
    setLoading(true)
    setSelectedCodes(new Set())
    try {
      const response = await queryScreening(text)
      add(text)
      setResult({ type: PAGE_EVENT_TYPES.stockScreening, ...response })
    } catch (err) {
      message.error(apiErrorMessage(err, '筛选失败，请稍后重试'))
    } finally {
      setLoading(false)
    }
  }

  const searchBox = (
    <ScreeningSearchBox
      value={query}
      onChange={setQuery}
      onSubmit={runSearch}
      loading={loading}
      history={history}
      onClearHistory={clear}
      hero={!result}
    />
  )

  if (!result) {
    return (
      <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center gap-8 p-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="flex items-center gap-3">
            <ThunderboltOutlined className="text-4xl text-blue-400" />
            <Typography.Title level={2} className="!mb-0">
              AI 选股
            </Typography.Title>
          </div>
          <Typography.Text type="secondary" className="text-base">
            输入条件，问财直查，即席筛选
          </Typography.Text>
        </div>
        <div className="w-full">{searchBox}</div>
        <Typography.Text type="secondary" className="text-xs">
          日期请带显式年份（如 2026年9月11日）；结果为临时内容，刷新后清除
        </Typography.Text>
      </div>
    )
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col gap-3 overflow-auto p-4">
      {searchBox}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <Space size={4} align="baseline">
          <Typography.Text strong>选出A股</Typography.Text>
          <Typography.Text className="text-2xl font-semibold text-red-500">
            {result.total}
          </Typography.Text>
          <Typography.Text type="secondary" className="text-xs">
            · 展示 {dataSource.length} 条 · 数据来源于同花顺问财
          </Typography.Text>
        </Space>
        <Space>
          <Button
            type="primary"
            disabled={selectedRows.length === 0}
            onClick={() => setModalOpen(true)}
          >
            加入自选分组{selectedRows.length > 0 ? `（${selectedRows.length}）` : ''}
          </Button>
          <Button
            onClick={() => {
              setResult(null)
              setSelectedCodes(new Set())
            }}
          >
            清除结果
          </Button>
        </Space>
      </div>

      {result.truncated && (
        <Alert
          type="warning"
          showIcon
          message={`命中 ${result.total} 只，仅展示前 ${dataSource.length} 条；可在上方修改问句收敛条件后重新搜索`}
        />
      )}

      {dataSource.length === 0 ? (
        <Empty
          description={
            <span>
              未命中任何股票（已自动放宽改写重试）
              <br />
              建议放宽或拆分条件、确认日期带显式年份、减少排除项后重新搜索
            </span>
          }
          className="py-16"
        />
      ) : (
        <Table<StockScreeningRow>
          rowKey="stockCode"
          size="small"
          bordered
          columns={tableColumns}
          dataSource={dataSource}
          loading={loading}
          scroll={{ x: 'max-content', y: 'calc(100vh - 360px)' }}
          pagination={{
            defaultPageSize: 50,
            pageSizeOptions: [20, 50, 100],
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            size: 'small',
          }}
          rowSelection={{
            selectedRowKeys: selectedRows.map((row) => row.stockCode),
            onChange: (keys) => setSelectedCodes(new Set(keys as string[])),
          }}
        />
      )}

      <AddToWatchlistModal
        open={modalOpen}
        stocks={selectedRows}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}
