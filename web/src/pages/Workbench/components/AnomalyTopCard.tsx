import { Empty, Spin, Tag, Tooltip } from 'antd'
import { Link } from 'react-router-dom'

import type { WorkbenchAnomalyTop } from '@ai-invest/shared'

import { changeColor, formatPercent } from '@/utils/formatters'

import { ANOMALY_TYPE_LABELS } from '@/pages/Anomaly/labels'

import { FoldCard } from './FoldCard'

interface AnomalyTopCardProps {
  anomalyTop?: WorkbenchAnomalyTop | null
  loading?: boolean
  className?: string
  stretch?: boolean
}

/** 检测维度中文标签，多个时展示首个 + 计数。 */
function typeBrief(types: string[]): string {
  if (!types.length) return '—'
  const labels = types.map((t) => ANOMALY_TYPE_LABELS[t] ?? t)
  return labels.length > 1 ? `${labels[0]} 等${labels.length}项` : labels[0]
}

/** 工作台异动速览卡：最新检测日板块/个股强度 Top5，窄列双段紧凑排布。 */
export function AnomalyTopCard({
  anomalyTop,
  loading,
  className,
  stretch,
}: AnomalyTopCardProps) {
  return (
    <FoldCard
      title={
        <span className="inline-flex items-center gap-2">
          异动速览
          {anomalyTop && (
            <span className="text-[11px] text-gray-500 font-mono font-normal">
              {anomalyTop.tradeDate}
            </span>
          )}
        </span>
      }
      extra={<Link to="/anomaly/sector" className="text-xs">异动中心</Link>}
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : !anomalyTop || (!anomalyTop.sectors.length && !anomalyTop.stocks.length) ? (
        <Empty description="暂无异动数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="flex flex-col gap-3">
          <section>
            <div className="text-[11px] text-gray-500 font-semibold mb-1">板块异动</div>
            {anomalyTop.sectors.length ? (
              anomalyTop.sectors.map((it) => (
                <div
                  key={`${it.sectorType}-${it.sectorCode}`}
                  className="flex items-center gap-2 text-xs py-1.5 border-b border-dashed border-gray-800 last:border-b-0"
                >
                  <Tooltip
                    title={`${typeBrief(it.anomalyTypes)}${it.attributionSummary ? ` · ${it.attributionSummary}` : ''}`}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      <Link
                        to={`/sector/${it.sectorType}/${it.sectorCode}`}
                        className="hover:underline"
                      >
                        {it.sectorName}
                      </Link>
                      <span className="ml-1.5 text-[10px] text-gray-500">
                        {typeBrief(it.anomalyTypes)}
                      </span>
                    </span>
                  </Tooltip>
                  <span className={`shrink-0 font-mono font-semibold ${changeColor(it.changePct)}`}>
                    {it.changePct != null ? formatPercent(it.changePct) : '-'}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-gray-500 py-1.5">暂无板块异动</div>
            )}
          </section>

          <section>
            <div className="text-[11px] text-gray-500 font-semibold mb-1">个股异动</div>
            {anomalyTop.stocks.length ? (
              anomalyTop.stocks.map((it) => (
                <div
                  key={it.stockCode}
                  className="flex items-center gap-2 text-xs py-1.5 border-b border-dashed border-gray-800 last:border-b-0"
                >
                  <Tooltip
                    title={`${typeBrief(it.anomalyTypes)}${it.attributionSummary ? ` · ${it.attributionSummary}` : ''}`}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      <Link to={`/stock/${it.stockCode}`} className="hover:underline">
                        {it.stockName}
                      </Link>
                      {it.isWatchlist && (
                        <Tag color="gold" className="!mr-0 !ml-1.5 !text-[10px] !leading-4 !px-1">
                          自选
                        </Tag>
                      )}
                      <span className="ml-1.5 text-[10px] text-gray-500">
                        {typeBrief(it.anomalyTypes)}
                      </span>
                    </span>
                  </Tooltip>
                  <span className={`shrink-0 font-mono font-semibold ${changeColor(it.changePct)}`}>
                    {it.changePct != null ? formatPercent(it.changePct) : '-'}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-gray-500 py-1.5">暂无个股异动</div>
            )}
          </section>

          <div className="pt-2 text-[10px] text-gray-600 border-t border-dashed border-gray-800">
            按异动强度排序 · 检测每日盘后自动运行
          </div>
        </div>
      )}
    </FoldCard>
  )
}
