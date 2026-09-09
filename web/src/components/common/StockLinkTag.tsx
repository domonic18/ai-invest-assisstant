import { Tag } from 'antd'
import { Link } from 'react-router-dom'

import { useColorScheme } from '@/stores/settings'
import { changeColor } from '@/utils/formatters'

interface StockLinkTagProps {
  /** 股票代码；为空时不可点击（如传导链中无法解析的原文）。 */
  code: string | null
  name: string
  /** 当日涨跌幅（%），scheme 着色；为空只显示名称。 */
  changePct: number | null
}

/** 股票标的 Tag：名称 + 当日涨跌幅，有代码时点击直达个股页（实时电报/传导链共用）。 */
export function StockLinkTag({ code, name, changePct }: StockLinkTagProps) {
  useColorScheme()
  const tag = (
    <Tag className="!m-0 !text-xs">
      {name}
      {changePct != null && (
        <span className={changeColor(changePct)}>
          {' '}
          {changePct >= 0 ? '+' : ''}
          {changePct.toFixed(2)}%
        </span>
      )}
    </Tag>
  )
  return code ? (
    <Link to={`/stock/${code}`} className="!text-xs">
      {tag}
    </Link>
  ) : (
    tag
  )
}
