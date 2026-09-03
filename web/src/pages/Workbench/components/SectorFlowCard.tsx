import { Link } from 'react-router-dom'

import { FoldCard } from './FoldCard'

/** 板块资金动向占位卡：数据由收盘后采集任务落库，完整视图在资金流向页。 */
export function SectorFlowCard() {
  return (
    <FoldCard title="板块资金动向">
      <div className="py-7 text-center text-xs text-gray-500">
        <span className="block text-2xl mb-2 opacity-50">◇</span>
        今日资金流向数据采集中，盘后自动更新
      </div>
      <div className="text-right">
        <Link to="/capital-flow" className="text-xs">查看资金流向 →</Link>
      </div>
    </FoldCard>
  )
}
