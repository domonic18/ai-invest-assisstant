import { RobotOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { Button, Empty, Popconfirm, Tag, Tooltip, message } from 'antd'
import type { ApiAgentWatchlistSelectionItem, WatchlistQuote } from '@ai-invest/shared'

import { useRemoveAgentSelection } from '@/hooks/useWatchlistGroups'
import { apiErrorMessage } from '@/utils/errorMessage'

interface AgentGroupPanelProps {
  groupName: string
  selections: ApiAgentWatchlistSelectionItem[]
  quotesByCode: Map<string, WatchlistQuote>
  selectedCode: string | null
  onSelect: (code: string) => void
}

/** 自选页 agent 分组：AI 徽标 + 选入依据 + 置信度 + 人工移出（全局生效）。 */
export function AgentGroupPanel({
  groupName,
  selections,
  quotesByCode,
  selectedCode,
  onSelect,
}: AgentGroupPanelProps) {
  const removeSelection = useRemoveAgentSelection()

  if (selections.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <Empty
          className="mt-10"
          description="交易 Agent 暂无选股（每个交易日 19:00 自动生成）"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto" role="listbox" aria-label={`${groupName}选股列表`}>
      {selections.map((item) => {
        const quote = quotesByCode.get(item.stockCode)
        const selected = item.stockCode === selectedCode
        return (
          <div
            key={item.id}
            role="option"
            aria-selected={selected}
            data-code={item.stockCode}
            onClick={() => onSelect(item.stockCode)}
            className={`flex items-start gap-2 px-3 py-2 border-b border-gray-800/60 cursor-pointer ${
              selected ? 'bg-[#1c1f26]' : 'hover:bg-[#15181e]'
            }`}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-sm text-gray-200">
                  {quote?.name ?? item.stockCode}
                </span>
                <span className="text-xs text-gray-500 font-mono shrink-0">
                  {item.stockCode}
                </span>
                <Tag className="!text-[10px] !mr-0 !leading-4 !px-1 shrink-0">
                  <RobotOutlined className="mr-0.5" />
                  AI
                </Tag>
              </div>
              <Tooltip title={item.reason} placement="bottomLeft">
                <div className="truncate text-xs text-gray-500 mt-0.5">{item.reason}</div>
              </Tooltip>
            </div>
            <div className="text-right shrink-0 flex items-center gap-1">
              {item.confidence != null && (
                <span
                  className="text-xs text-gray-400 font-mono"
                  title="AI 选入置信度"
                >
                  {(item.confidence * 100).toFixed(0)}%
                </span>
              )}
              <span onClick={(e) => e.stopPropagation()}>
                <Popconfirm
                  title="移出 AI 选股"
                  description="移出后全局生效，Agent 次日不会再选入该股。确定移出？"
                  okText="移出"
                  cancelText="取消"
                  onConfirm={() =>
                    removeSelection.mutate(item.id, {
                      onSuccess: () => message.success('已移出，次日不再选入'),
                      onError: (err) => message.error(apiErrorMessage(err, '移出失败')),
                    })
                  }
                >
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<MinusCircleOutlined />}
                    aria-label={`移出 ${quote?.name ?? item.stockCode}`}
                  />
                </Popconfirm>
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
