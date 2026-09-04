import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Card, DatePicker, Input, Select } from 'antd'
import type { Dayjs } from 'dayjs'

import { REPORT_TYPE_OPTIONS } from '../utils'

interface FinancialReportFiltersProps {
  keyword: string
  range: [Dayjs | null, Dayjs | null] | null
  reportType?: string
  onKeywordChange: (value: string) => void
  onRangeChange: (value: [Dayjs | null, Dayjs | null] | null) => void
  onReportTypeChange: (reportType?: string) => void
  onSearch: () => void
  onCollect: () => void
}

/** 筛选与采集单行工具栏（原型 fr-toolbar 规格）。 */
export function FinancialReportFilters({
  keyword,
  range,
  reportType,
  onKeywordChange,
  onRangeChange,
  onReportTypeChange,
  onSearch,
  onCollect,
}: FinancialReportFiltersProps) {
  return (
    <Card variant="borderless" size="small">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="代码 / 名称"
          allowClear
          className="w-full sm:w-52"
          value={keyword}
          onChange={(e) => onKeywordChange(e.target.value)}
          onPressEnter={onSearch}
        />
        <Select
          className="w-full sm:w-32"
          value={reportType ?? ''}
          onChange={(value) => onReportTypeChange(value || undefined)}
          options={[
            { value: '', label: '全部类型' },
            ...REPORT_TYPE_OPTIONS,
          ]}
        />
        <DatePicker.RangePicker
          className="w-full sm:w-auto"
          value={range}
          onChange={(value) => onRangeChange(value)}
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>
          查询
        </Button>
        <div className="flex-1" />
        <Button icon={<PlusOutlined />} onClick={onCollect}>
          触发采集
        </Button>
      </div>
    </Card>
  )
}
