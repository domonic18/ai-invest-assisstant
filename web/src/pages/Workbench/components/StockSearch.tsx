import { SearchOutlined } from '@ant-design/icons'
import { AutoComplete, Input } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useStockSearch } from '@/hooks/useStocks'

/** 工作台全局股票搜索：名称/代码模糊匹配，选中跳转个股详情。 */
export function StockSearch() {
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(keyword.trim()), 300)
    return () => clearTimeout(timer)
  }, [keyword])

  const { data: stocks, isFetching } = useStockSearch(debounced)

  const options = (stocks ?? []).map((stock) => ({
    value: stock.code,
    label: (
      <div className="flex items-center justify-between gap-3">
        <span className="truncate">{stock.name}</span>
        <span className="font-mono text-xs text-gray-500">{stock.code}</span>
      </div>
    ),
  }))

  return (
    <AutoComplete
      value={keyword}
      options={options}
      filterOption={false}
      onChange={setKeyword}
      onSelect={(code: string) => {
        navigate(`/stock/${code}`)
        setKeyword('')
      }}
      className="w-full sm:max-w-xs"
      popupMatchSelectWidth={320}
      notFoundContent={debounced && !isFetching ? '无匹配股票' : null}
    >
      <Input
        placeholder="搜索股票名称 / 代码"
        prefix={<SearchOutlined className="text-gray-500" />}
        allowClear
      />
    </AutoComplete>
  )
}
