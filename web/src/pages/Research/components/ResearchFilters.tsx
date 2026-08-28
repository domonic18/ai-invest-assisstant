import { SearchOutlined } from '@ant-design/icons'
import { Button, Card, DatePicker, Input, Select, Tag } from 'antd'
import type { Dayjs } from 'dayjs'

import { useResearchFilters } from '@/hooks/useResearch'

interface ResearchFiltersProps {
  keyword: string
  industry?: string
  range: [Dayjs | null, Dayjs | null] | null
  broker?: string
  total: number
  onKeywordChange: (value: string) => void
  onIndustryChange: (value?: string) => void
  onRangeChange: (value: [Dayjs | null, Dayjs | null] | null) => void
  onBrokerChange: (broker?: string) => void
  onSearch: () => void
}

export function ResearchFilters({
  keyword,
  industry,
  range,
  broker,
  total,
  onKeywordChange,
  onIndustryChange,
  onRangeChange,
  onBrokerChange,
  onSearch,
}: ResearchFiltersProps) {
  const { data: filters } = useResearchFilters()

  return (
    <>
      <Card variant="borderless" size="small">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="搜索研报标题、公司、行业…"
            allowClear
            className="w-full sm:w-60"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
            onPressEnter={onSearch}
          />
          <Select
            placeholder="全部行业"
            allowClear
            className="w-full sm:w-40"
            value={industry}
            onChange={(value) => onIndustryChange(value ?? undefined)}
            options={(filters?.industries ?? []).map((item) => ({
              label: item,
              value: item,
            }))}
          />
          <DatePicker.RangePicker
            className="w-full sm:w-auto"
            value={range}
            onChange={(value) => onRangeChange(value)}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>
            查询
          </Button>
          <span className="text-xs text-gray-400">共 {total} 篇研报</span>
        </div>
      </Card>

      <div>
        <div className="text-xs text-gray-400 mb-2">券商</div>
        <div className="flex flex-wrap gap-2">
          <Tag.CheckableTag checked={!broker} onChange={() => onBrokerChange(undefined)}>
            全部
          </Tag.CheckableTag>
          {(filters?.brokers ?? []).map((item) => (
            <Tag.CheckableTag
              key={item}
              checked={broker === item}
              onChange={() => onBrokerChange(item)}
            >
              {item}
            </Tag.CheckableTag>
          ))}
        </div>
      </div>
    </>
  )
}
