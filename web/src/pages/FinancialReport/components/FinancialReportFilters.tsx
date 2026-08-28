import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Card, DatePicker, Input, Tag } from 'antd'
import type { Dayjs } from 'dayjs'

import { REPORT_TYPE_OPTIONS } from '../utils'

interface FinancialReportFiltersProps {
  keyword: string
  range: [Dayjs | null, Dayjs | null] | null
  reportType?: string
  total: number
  onKeywordChange: (value: string) => void
  onRangeChange: (value: [Dayjs | null, Dayjs | null] | null) => void
  onReportTypeChange: (reportType?: string) => void
  onSearch: () => void
  onCollect: () => void
}

export function FinancialReportFilters({
  keyword,
  range,
  reportType,
  total,
  onKeywordChange,
  onRangeChange,
  onReportTypeChange,
  onSearch,
  onCollect,
}: FinancialReportFiltersProps) {
  return (
    <>
      <Card variant="borderless" size="small">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="搜索财报标题、股票名称或代码…"
            allowClear
            className="w-full sm:w-60"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
            onPressEnter={onSearch}
          />
          <DatePicker.RangePicker
            className="w-full sm:w-auto"
            value={range}
            onChange={(value) => onRangeChange(value)}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>
            查询
          </Button>
          <span className="text-xs text-gray-400">共 {total} 份财报</span>
          <div className="flex-1" />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={onCollect}
          >
            采集财报
          </Button>
        </div>
      </Card>

      <div>
        <div className="text-xs text-gray-400 mb-2">报告类型</div>
        <div className="flex flex-wrap gap-2">
          <Tag.CheckableTag
            checked={!reportType}
            onChange={() => onReportTypeChange(undefined)}
          >
            全部
          </Tag.CheckableTag>
          {REPORT_TYPE_OPTIONS.map((option) => (
            <Tag.CheckableTag
              key={option.value}
              checked={reportType === option.value}
              onChange={() => onReportTypeChange(option.value)}
            >
              {option.label}
            </Tag.CheckableTag>
          ))}
        </div>
      </div>
    </>
  )
}
