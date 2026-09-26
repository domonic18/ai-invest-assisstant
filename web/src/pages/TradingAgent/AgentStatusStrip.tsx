/**
 * 模拟管理运行状态条：一屏回答「agent 是否在正常运行」。
 *
 * 三块信息：agent 专属账户绑定（未绑定时告警跳转账户 tab）、盘中自主执行
 * 总闸、三个定时任务（盘后同步/盘后复盘/每日计划）最近一次运行状态与时间
 * （collector_log 按 task_name 取最新一条，复用 useCollectorLogs）。
 */
import { CheckCircleFilled, CloseCircleFilled, LoadingOutlined, MinusCircleFilled } from '@ant-design/icons'
import { Button, Spin, Tag, Tooltip, Typography } from 'antd'

import { useAdminPaperTradeAccounts } from '@/hooks/usePaperTrade'
import { useCollectorLogs } from '@/hooks/useCollectorAdmin'
import { useAgentKey } from './agentKeyContext'
import { useTradingAgentConfig } from '@/hooks/useTradingAgent'
import { formatRelativeTime } from '@/utils/formatters'

const TASKS: { taskName: string; label: string }[] = [
  { taskName: 'paper-trade-sync', label: '盘后同步' },
  { taskName: 'paper-trade-review', label: '盘后复盘' },
  { taskName: 'agent-daily-plan', label: '每日计划' },
]

const STATUS_META: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
  success: { color: '#52c41a', icon: <CheckCircleFilled />, text: '成功' },
  partial: { color: '#faad14', icon: <CheckCircleFilled />, text: '部分成功' },
  failed: { color: '#ff4d4f', icon: <CloseCircleFilled />, text: '失败' },
  skipped: { color: '#8c8c8c', icon: <MinusCircleFilled />, text: '跳过' },
  running: { color: '#1677ff', icon: <LoadingOutlined />, text: '运行中' },
  pending: { color: '#1677ff', icon: <LoadingOutlined />, text: '排队中' },
}

function TaskStatus({ taskName, label }: { taskName: string; label: string }) {
  const { data } = useCollectorLogs({ taskName, pageSize: 1 })
  const log = data?.items[0]
  const meta = log ? (STATUS_META[log.status] ?? STATUS_META.skipped) : null
  return (
    <Tooltip
      title={
        log
          ? `${log.status === 'skipped' && log.message ? log.message : meta?.text}${log.finishedAt ? ` · ${formatRelativeTime(log.finishedAt)}` : ''}`
          : '暂无运行记录'
      }
    >
      <span className="inline-flex cursor-default items-center gap-1 text-xs">
        {meta ? (
          <span style={{ color: meta.color, fontSize: 12 }}>{meta.icon}</span>
        ) : (
          <MinusCircleFilled className="text-white/25" />
        )}
        <span className="text-white/60">{label}</span>
        {log?.startedAt && (
          <span className="text-white/40">{formatRelativeTime(log.startedAt)}</span>
        )}
      </span>
    </Tooltip>
  )
}

export function AgentStatusStrip({ onOpenAccounts }: { onOpenAccounts: () => void }) {
  const { data: accounts } = useAdminPaperTradeAccounts()
  const agentKey = useAgentKey()
  const { data: config } = useTradingAgentConfig(agentKey)
  const agentAccount = accounts?.items.find((account) => account.agentKey === agentKey)

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5">
      {agentAccount ? (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <CheckCircleFilled style={{ color: '#52c41a', fontSize: 12 }} />
          <span className="text-white/60">Agent 账户</span>
          <Typography.Text strong className="text-xs">
            {agentAccount.name}
          </Typography.Text>
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <CloseCircleFilled style={{ color: '#faad14', fontSize: 12 }} />
          <span className="text-white/60">Agent 账户未绑定</span>
          <Button size="small" type="link" className="!px-1 !text-xs" onClick={onOpenAccounts}>
            去绑定
          </Button>
        </span>
      )}
      <span className="inline-flex items-center gap-1.5 text-xs">
        <span className="text-white/60">盘中自主执行</span>
        {config ? (
          <Tag color={config.autoExecEnabled ? 'processing' : 'default'} className="!mr-0">
            {config.autoExecEnabled ? '开' : '关'}
          </Tag>
        ) : (
          <Spin size="small" />
        )}
      </span>
      <span className="inline-flex items-center gap-4">
        {TASKS.map((task) => (
          <TaskStatus key={task.taskName} {...task} />
        ))}
      </span>
    </div>
  )
}
