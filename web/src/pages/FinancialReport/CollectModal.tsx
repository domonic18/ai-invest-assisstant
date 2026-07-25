import { Alert, Button, Checkbox, DatePicker, Modal, Select, Spin, message } from 'antd'
import type { Dayjs } from 'dayjs'
import { useEffect, useState } from 'react'

import { searchStocks } from '@/api/stocks'
import {
  useCollectFinancialReport,
  useFinancialReportCollectLog,
} from '@/hooks/useFinancialReport'

const REPORT_TYPE_OPTIONS = [
  { value: 'annual', label: '年报' },
  { value: 'semi_annual', label: '半年报' },
  { value: 'q1', label: '一季报' },
  { value: 'q3', label: '三季报' },
]

interface StockOption {
  value: string
  label: string
}

interface CollectModalProps {
  open: boolean
  onClose: () => void
  onCollected: () => void
}

export function CollectModal({ open, onClose, onCollected }: CollectModalProps) {
  const [stockOptions, setStockOptions] = useState<StockOption[]>([])
  const [stockCode, setStockCode] = useState<string>()
  const [reportTypes, setReportTypes] = useState<string[]>([])
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [logId, setLogId] = useState<number | null>(null)
  const [searching, setSearching] = useState(false)

  const collectMutation = useCollectFinancialReport()
  const { data: log } = useFinancialReportCollectLog(logId)

  const reset = () => {
    setStockCode(undefined)
    setReportTypes([])
    setRange(null)
    setLogId(null)
  }

  useEffect(() => {
    if (!log) return
    if (log.status === 'success') {
      message.success(`采集完成，入库 ${log.records_count} 条`)
      onCollected()
      reset()
      onClose()
    } else if (log.status === 'failed') {
      message.error(log.error_msg ?? '采集失败')
      setLogId(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [log?.status])

  const handleSearchStock = async (keyword: string) => {
    if (!keyword) {
      setStockOptions([])
      return
    }
    setSearching(true)
    try {
      const stocks = await searchStocks({ q: keyword, limit: 10 })
      setStockOptions(
        stocks.map((stock) => ({
          value: stock.code,
          label: `${stock.name}（${stock.code}）`,
        })),
      )
    } catch {
      setStockOptions([])
    } finally {
      setSearching(false)
    }
  }

  const handleSubmit = async () => {
    if (!stockCode) {
      message.warning('请选择要采集的股票')
      return
    }
    const [start, end] = range ?? []
    try {
      const result = await collectMutation.mutateAsync({
        stock_code: stockCode,
        report_types: reportTypes.length > 0 ? reportTypes : null,
        start_date: start ? start.format('YYYY-MM-DD') : null,
        end_date: end ? end.format('YYYY-MM-DD') : null,
      })
      setLogId(result.log_id)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '采集任务提交失败')
    }
  }

  const collecting = logId != null
  const inFlight = collecting && log?.status !== 'failed'

  return (
    <Modal
      title="采集财报"
      open={open}
      onCancel={() => {
        reset()
        onClose()
      }}
      footer={null}
      width={480}
      destroyOnHidden
    >
      <div className="space-y-4 py-2">
        <div>
          <div className="text-sm text-gray-600 mb-1">股票</div>
          <Select
            showSearch
            placeholder="输入代码或名称搜索"
            className="w-full"
            value={stockCode}
            options={stockOptions}
            loading={searching}
            filterOption={false}
            onSearch={handleSearchStock}
            onChange={(value) => setStockCode(value)}
            disabled={inFlight}
          />
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">报告类型（不选则为全部）</div>
          <Checkbox.Group
            options={REPORT_TYPE_OPTIONS}
            value={reportTypes}
            onChange={(values) => setReportTypes(values as string[])}
            disabled={inFlight}
          />
        </div>
        <div>
          <div className="text-sm text-gray-600 mb-1">披露日期范围（可选）</div>
          <DatePicker.RangePicker
            className="w-full"
            value={range}
            onChange={(value) => setRange(value)}
            disabled={inFlight}
          />
        </div>

        {collecting && log && log.status !== 'failed' && (
          <Alert
            type={log.status === 'success' ? 'success' : 'info'}
            message={
              log.status === 'success' ? (
                `采集完成，入库 ${log.records_count} 条`
              ) : (
                <span className="inline-flex items-center gap-2">
                  <Spin size="small" /> 采集中，通常需要几十秒，请稍候…
                </span>
              )
            }
          />
        )}

        <div className="flex justify-end gap-2">
          <Button
            onClick={() => {
              reset()
              onClose()
            }}
          >
            取消
          </Button>
          <Button
            type="primary"
            loading={collectMutation.isPending || inFlight}
            disabled={!stockCode}
            onClick={handleSubmit}
          >
            {inFlight ? '采集中…' : '开始采集'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
