import { SearchOutlined } from '@ant-design/icons'
import { AutoComplete, Button, Input } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useStockSearch } from '@/hooks/useStocks'

interface StockSearchProps {
  /** 输入框占满容器宽度（移动端搜索抽屉内使用），默认固定 260px。 */
  fluid?: boolean
  /** 选中股票跳转详情后回调（移动端抽屉关闭用）。 */
  onNavigated?: () => void
}

/** 全局顶栏股票搜索（原型 header-search）：名称/代码模糊匹配，选中跳转个股详情。 */
export function StockSearch({ fluid = false, onNavigated }: StockSearchProps) {
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
    onNavigated?.()
  }

  const handleSearch = () => {
    const q = keyword.trim()
    if (!q) return
    if (/^\d{5,6}$/.test(q)) {
      goStock(q)
      return
    }
    if (stocks?.length === 1) goStock(stocks[0].code)
  }

  return (
    <div className={`flex items-center gap-2 ${fluid ? 'w-full' : ''}`}>
      <AutoComplete
        value={keyword}
        options={options}
        filterOption={false}
        onChange={setKeyword}
        onSelect={goStock}
        className={fluid ? 'flex-1' : 'w-[260px]'}
        popupMatchSelectWidth={fluid ? false : 320}
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
