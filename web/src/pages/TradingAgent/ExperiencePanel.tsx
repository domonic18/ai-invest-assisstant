/**
 * Agent 经验总结（智体中枢页 tab）：读取 agent_memory 记忆库
 * （复盘自动沉淀 + 手动沉淀，批次 9），active 条目每日计划生成时注入 Agent。
 */
import { Alert, Card, Empty, Skeleton, Tag, Typography } from 'antd'

import type { AgentMemoryType, ApiAgentMemory } from '@ai-invest/shared'

import { useAgentKey } from './agentKeyContext'
import { useTradingAgentMemories } from '@/hooks/useTradingAgent'
import { formatDateTime } from '@/utils/formatters'

const MEM_TYPE_META: Record<AgentMemoryType, { label: string; color: string }> = {
  discipline: { label: '纪律', color: 'gold' },
  method: { label: '方法', color: 'processing' },
  lesson: { label: '教训', color: 'error' },
}

function ExperienceItem({ memory }: { memory: ApiAgentMemory }) {
  const memType = MEM_TYPE_META[memory.memType] ?? { label: memory.memType, color: 'default' }
  const archived = memory.status === 'archived'
  return (
    <div
      className={`rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 ${
        archived ? 'opacity-55' : ''
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Tag color={memType.color} className="!mr-0">
          {memType.label}
        </Tag>
        <Typography.Text strong className="text-sm">
          {memory.title}
        </Typography.Text>
        <Tag className="!mr-0 !text-[10px]">{memory.source === 'manual' ? '手动' : '复盘'}</Tag>
        {archived && <Tag className="!mr-0 !text-[10px]">已停用</Tag>}
        <span className="ml-auto text-xs text-white/40">{formatDateTime(memory.updatedAt)}</span>
      </div>
      <Typography.Paragraph className="!mb-0 mt-1 text-xs text-white/60">
        {memory.body}
      </Typography.Paragraph>
    </div>
  )
}

export function ExperiencePanel() {
  const agentKey = useAgentKey()
  const { data: memories, isLoading } = useTradingAgentMemories(agentKey)

  return (
    <Card size="small" title="经验总结">
      <Alert
        type="info"
        showIcon
        className="!mb-3"
        message="经验库（复盘自动沉淀 + 手动沉淀），active 条目每日计划生成时注入 Agent。"
      />
      {isLoading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : (memories ?? []).length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无经验总结（盘后复盘生成后自动沉淀，也可在记忆面板手动添加）"
        />
      ) : (
        <div className="space-y-2">
          {(memories ?? []).map((memory) => (
            <ExperienceItem key={memory.id} memory={memory} />
          ))}
        </div>
      )}
    </Card>
  )
}
