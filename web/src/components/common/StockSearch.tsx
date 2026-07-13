import { SearchOutlined } from '@ant-design/icons'
import { AutoComplete, Input } from 'antd'
import { useState } from 'react'

import { useStockSearch } from '@/hooks/useStocks'

interface StockSearchProps {
  onSelect: (code: string) => void
  placeholder?: string
}

export function StockSearch({ onSelect, placeholder = '搜索股票代码/名称' }: StockSearchProps) {
  const [query, setQuery] = useState('')
  const { data: stocks } = useStockSearch(query, query.length >= 2)

  const options =
    stocks?.map((stock) => ({
      value: stock.code,
      label: `${stock.name} (${stock.code})`,
    })) || []

  return (
    <AutoComplete
      options={options}
      onSearch={setQuery}
      onSelect={onSelect}
      placeholder={placeholder}
      className="w-64"
    >
      <Input prefix={<SearchOutlined />} />
    </AutoComplete>
  )
}
