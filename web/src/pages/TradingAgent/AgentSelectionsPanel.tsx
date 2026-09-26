/**
 * 「Agent 自选」卡片（自选页 agent 分组迁入模拟管理）：AI 选股清单
 * （代码 + 选入日 + 依据 + 置信度）与人工移出（全局生效，次日不重选）。
 * 响应为单分组对象，未来多 agent 各持分组时后端扩为列表、此处平铺渲染。
 */
import { MinusCircleOutlined, RobotOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Popconfirm, Tag, Tooltip } from 'antd'
import { useNavigate } from 'react-router-dom'

import type { ApiAgentWatchlistSelectionItem } from '@ai-invest/shared'

import {
  useRemoveTradingAgentSelection,
  useTradingAgentSelections,
} from '@/hooks/useTradingAgent'

function SelectionRow({ item }: { item: ApiAgentWatchlistSelectionItem }) {
  const navigate = useNavigate()
  const remove = useRemoveTradingAgentSelection()

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="flex items-center gap-2">
        <Tag color="geekblue" className="!mr-0">
          <RobotOutlined className="mr-0.5" />
          AI
        </Tag>
        <Button
          type="text"
          size="small"
          className="!px-0 font-mono"
          onClick={() => navigate(`/stock/${item.stockCode}`)}
        >
          {item.stockCode}
        </Button>
        <span className="text-xs text-gray-500">选入 {item.tradeDate}</span>
        <span className="ml-auto" />
        {item.confidence != null && (
          <span className="text-xs text-gray-400 font-mono" title="AI 选入置信度">
            {(item.confidence * 100).toFixed(0)}%
          </span>
        )}
        <Popconfirm
          title="移出 AI 选股"
          description="移出后全局生效，Agent 次日不会再选入该股。确定移出？"
          okText="移出"
          cancelText="取消"
          onConfirm={() => remove.mutate(item.id)}
        >
          <Button
            type="text"
            size="small"
            danger
            icon={<MinusCircleOutlined />}
            aria-label={`移出 ${item.stockCode}`}
          />
        </Popconfirm>
      </div>
      <Tooltip title={item.reason} placement="bottomLeft">
        <div className="mt-1 truncate text-xs text-gray-300">{item.reason}</div>
      </Tooltip>
    </div>
  )
}

export function AgentSelectionsPanel() {
  const { data: group, isLoading } = useTradingAgentSelections()
  const selections = group?.items ?? []

  return (
    <Card size="small" title={group?.name ?? 'Agent 自选'}>
      {isLoading ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="加载中…"
        />
      ) : selections.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无选股（每个交易日 19:00 自动生成，也可在对话中制定）"
        />
      ) : (
        <div className="space-y-2">
          {selections.map((item) => (
            <SelectionRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </Card>
  )
}
