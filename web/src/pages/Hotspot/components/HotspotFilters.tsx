import { SearchOutlined } from '@ant-design/icons'
import { Button, DatePicker, Form, Input } from 'antd'
import type { Dayjs } from 'dayjs'

export interface FilterForm {
  sectorType?: string
  tradeDate?: Dayjs | null
}

interface HotspotFiltersProps {
  form: ReturnType<typeof Form.useForm<FilterForm>>[0]
  onSearch: (values: FilterForm) => void
}

export function HotspotFilters({ form, onSearch }: HotspotFiltersProps) {
  return (
    <Form form={form} layout="inline" onFinish={onSearch} className="mb-4">
      <Form.Item name="sectorType" label="板块类型">
        <Input placeholder="industry / concept" allowClear />
      </Form.Item>
      <Form.Item name="tradeDate" label="交易日期">
        <DatePicker />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
          查询
        </Button>
      </Form.Item>
    </Form>
  )
}
