/**
 * Agent 运行态徽标（D32）：working=蓝色 Loading 脉冲 / produced_today=绿色
 * 对勾 / idle=灰色时钟 / paused=琥珀暂停 / off=置灰暂停。文案优先用后端
 * state_label（含作业内容或下次时刻），后端算真实状态，前端不虚报「工作中」。
 */
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  LoadingOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons'
import { Tooltip } from 'antd'
import type { ReactNode } from 'react'

import type { AgentRuntimeState } from '@ai-invest/shared'

const STATE_META: Record<AgentRuntimeState, { color: string; icon: ReactNode; text: string }> = {
  working: { color: '#1677ff', icon: <LoadingOutlined />, text: '作业中' },
  produced_today: { color: '#52c41a', icon: <CheckCircleFilled />, text: '今日已产出' },
  idle: { color: '#8c8c8c', icon: <ClockCircleOutlined />, text: '待命' },
  paused: { color: '#faad14', icon: <PauseCircleOutlined />, text: '已暂停' },
  off: { color: '#595959', icon: <PauseCircleOutlined />, text: '未启用' },
}

export function StateBadge({
  state,
  label,
}: {
  state: AgentRuntimeState
  label?: string | null
}) {
  const meta = STATE_META[state]
  const text = label ?? meta.text
  return (
    <Tooltip title={text}>

      <span
        className="inline-flex max-w-full items-center gap-1 text-xs"
        style={{ color: meta.color, opacity: state === 'off' ? 0.75 : 1 }}
      >
        <span className={state === 'working' ? 'animate-pulse' : undefined}>{meta.icon}</span>
        <span className="truncate">{text}</span>
      </span>
    </Tooltip>
  )
}

export { STATE_META as AGENT_STATE_META }
