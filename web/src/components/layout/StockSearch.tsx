import { SearchOutlined } from '@ant-design/icons'
import { AutoComplete, Button, Input } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useStockSearch } from '@/hooks/useStocks'

/** 全局顶栏股票搜索（原型 header-search）：名称/代码模糊匹配，选中跳转个股详情。 */
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

  const goStock = (code: string) => {
    navigate(`/stock/${code}`)
    setKeyword('')
  }

  const handleSearch = () => {
    const q = keyword.trim()
    if (!q) return
    if (/^\d{6}$/.test(q)) {
      goStock(q)
      return
    }
    if (stocks?.length === 1) goStock(stocks[0].code)
  }

  return (
    <div className="flex items-center gap-2">
      <AutoComplete
        value={keyword}
        options={options}
        filterOption={false}
        onChange={setKeyword}
        onSelect={goStock}
        className="w-[260px]"
        popupMatchSelectWidth={320}
        notFoundContent={debounced && !isFetching ? '无匹配股票' : null}
      >
        <Input
          placeholder="搜索股票代码或名称…"
          prefix={<SearchOutlined className="text-gray-500" />}
          onPressEnter={handleSearch}
          allowClear
        />
      </AutoComplete>
      <Button type="primary" onClick={handleSearch}>
        搜索
      </Button>
    </div>
  )
}
