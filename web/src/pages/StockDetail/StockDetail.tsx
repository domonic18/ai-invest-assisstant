import { useParams } from 'react-router-dom'

import { ErrorState } from './components/ErrorState'
import { StockDetailContent } from './StockDetailContent'

export function StockDetail() {
  const { code } = useParams<{ code?: string }>()

  if (!code) {
    return <ErrorState message="未指定股票代码" />
  }

  return <StockDetailContent stockCode={code} />
}
