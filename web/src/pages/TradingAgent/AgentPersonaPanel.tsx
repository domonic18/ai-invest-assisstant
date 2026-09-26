/**
 * 会话人设面板（D30）：模板换绑 Select + YAML 原文只读浏览。
 * 人设 YAML 是硬纪律骨架；身份（名称/标语/策略）由注册表运行时注入，
 * 方法论基座在会话 system prompt 单独成段（配置页「作业技能」区可视化）。
 */
import { Alert, Card, Select, Skeleton, Typography } from 'antd'

import { useAgentKey } from './agentKeyContext'
import {
  useTradingAgentConfig,
  useTradingAgentPrompt,
  useTradingAgentPromptTemplates,
  useUpdateTradingAgentConfig,
} from '@/hooks/useTradingAgent'

export function AgentPersonaPanel() {
  const agentKey = useAgentKey()
  const { data: config } = useTradingAgentConfig(agentKey)
  const templates = useTradingAgentPromptTemplates()
  const promptQ = useTradingAgentPrompt(agentKey)
  const update = useUpdateTradingAgentConfig(agentKey)

  const label = promptQ.data?.label ?? config?.promptId

  return (
    <Card
      size="small"
      title="会话人设"
      extra={
        <Select
          size="small"
          className="min-w-44"
          loading={templates.isLoading || update.isPending}
          value={config?.promptId}
          options={(templates.data ?? []).map((t) => ({ value: t.promptId, label: t.label }))}
          onChange={(promptId) => update.mutate({ promptId })}
        />
      }
    >
      <Alert
        type="info"
        showIcon
        className="!mb-3"
        message="人设 YAML 定义对话身份骨架与硬纪律；名称/策略等注册信息运行时注入，换绑立即生效（会话自动重建）。"
      />
      {promptQ.isLoading || !promptQ.data ? (
        <div className="flex justify-center py-6">
          <Skeleton active title={false} paragraph={{ rows: 4 }} />
        </div>
      ) : (
        <>
          <Typography.Text type="secondary" className="text-xs">
            当前模板：{label}（YAML 原文，只读）
          </Typography.Text>
          <pre className="mt-2 max-h-[420px] overflow-auto rounded-md border border-white/10 bg-black/30 p-3 text-xs leading-relaxed whitespace-pre-wrap text-[#9ecbff]">
            {promptQ.data.content}
          </pre>
        </>
      )}
    </Card>
  )
}
