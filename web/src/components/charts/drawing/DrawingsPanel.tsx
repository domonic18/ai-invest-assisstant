/**
 * 画线清单面板：用户画线组（选中/删除）+ AI 画线组（来源徽标 + 采纳）。
 * 数据由集成层按当前周期过滤后传入（period 是归属键，严格隔离）。
 */

import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { Empty, Tooltip } from 'antd'

import type { AiKlineDrawingGroup, UserKlineDrawing } from './types'
import { DIRECTION_LABEL, DRAWING_TYPE_LABEL } from './types'

const TYPE_EMOJI: Record<string, string> = {
  trendline: '╱',
  ray: '→',
  hline: '─',
  box: '▭',
  text: 'T',
}

export interface DrawingsPanelProps {
  drawings: UserKlineDrawing[]
  aiGroups: AiKlineDrawingGroup[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  onDelete: (id: string) => void
  onAdopt: (item: { label: string; period: AiKlineDrawingGroup['period'] }) => void
}

function summarize(d: UserKlineDrawing): string {
  const a = d.anchors
  if (d.drawingType === 'hline') return `@ ${a[0].price}`
  if (d.drawingType === 'box') return `${a[0].price} ~ ${a[1].price}`
  if (d.drawingType === 'text') return a[0].date
  return `${a[0].date} → ${a[1].date}`
}

export function DrawingsPanel({
  drawings,
  aiGroups,
  selectedId,
  onSelect,
  onDelete,
  onAdopt,
}: DrawingsPanelProps) {
  if (drawings.length === 0 && aiGroups.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无画线" />
  }
  return (
    <div className="flex flex-col gap-3 text-xs">
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="font-medium text-gray-300">用户画线</span>
          <span className="text-gray-500">{drawings.length}</span>
        </div>
        {drawings.length === 0 ? (
          <div className="rounded border border-dashed border-white/10 px-2 py-2 text-center text-gray-500">
            选择上方工具在图上绘制
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {drawings.map((d) => (
              <li
                key={d.id}
                className="group flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-white/[0.04]"
                style={{
                  border: `1px solid ${selectedId === d.id ? '#5e6ad2' : 'transparent'}`,
                  background: selectedId === d.id ? 'rgba(94,106,210,0.10)' : undefined,
                }}
                onClick={() => onSelect(selectedId === d.id ? null : d.id)}
              >
                <span style={{ color: d.style.color }}>{TYPE_EMOJI[d.drawingType]}</span>
                <span className="flex-1 truncate text-gray-300">
                  {d.text || DRAWING_TYPE_LABEL[d.drawingType]}
                  {d.drawingType === 'ray' && d.direction && d.direction !== 'right'
                    ? `（${DIRECTION_LABEL[d.direction]}）`
                    : ''}
                </span>
                <span className="text-[10px] text-gray-500">{summarize(d)}</span>
                <Tooltip title="删除">
                  <CloseOutlined
                    className="ml-1 hidden text-gray-500 hover:text-red-400 group-hover:inline"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(d.id)
                    }}
                  />
                </Tooltip>
              </li>
            ))}
          </ul>
        )}
      </div>

      {aiGroups.map((group) => (
        <div key={`${group.targetType}-${group.targetCode}-${group.period}`} className="border-t border-dashed border-white/10 pt-2">
          <div className="mb-1.5 flex items-center gap-1.5">
            <span className="rounded border border-[#5e6ad2] px-1 text-[9px] font-bold text-[#8a93ff]">AI</span>
            <span className="font-medium text-gray-300">AI 画线</span>
            <Tooltip title={`${group.skillId} · ${group.tradeDate ?? ''} 对话生成 · 全局共享`}>
              <span className="truncate text-[10px] text-gray-500">
                {group.skillId} · {group.tradeDate ?? ''}
              </span>
            </Tooltip>
          </div>
          {group.summary && <p className="mb-1.5 leading-relaxed text-gray-400">{group.summary}</p>}
          <ul className="flex flex-col gap-1">
            {group.drawings.map((item) => (
              <li
                key={item.label}
                className="group flex items-center gap-2 rounded px-2 py-1 hover:bg-white/[0.04]"
              >
                <span className="text-[#7b85ff]">{TYPE_EMOJI[item.drawingType]}</span>
                <Tooltip title={item.reason}>
                  <span className="flex-1 truncate text-gray-300">{item.label}</span>
                </Tooltip>
                <button
                  type="button"
                  className="inline-flex items-center gap-0.5 rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-gray-300 hover:border-[#5e6ad2] hover:text-[#aeb4ff]"
                  onClick={() => onAdopt({ label: item.label, period: group.period })}
                >
                  <CheckOutlined />采纳
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
