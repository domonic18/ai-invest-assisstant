/**
 * 对话对象头像（顶栏与切换器共用，保证「顶部头像 = 当前对话对象」）：
 * assistant = 助手头像；交易 Agent 按 promptId 原型取头像，未登记原型回落
 * accentColor + 名称首字方块。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

import { AGENT_PROMPT_AVATARS, ASSISTANT_AVATAR, ASSISTANT_FALLBACK_COLOR } from './agentAvatars'

export function ChatAgentAvatar({
  agentType,
  items,
  size = 32,
}: {
  /** 当前对话对象：'assistant' 或 agent_key。 */
  agentType: string
  items: AgentOverviewItem[]
  size?: number
}) {
  const item = items.find((i) => i.profile.agentKey === agentType)
  const avatar =
    agentType === 'assistant' ? ASSISTANT_AVATAR : item ? AGENT_PROMPT_AVATARS[item.profile.promptId] : undefined
  if (avatar) {
    return (
      <img
        src={avatar}
        alt=""
        draggable={false}
        style={{ width: size, height: size }}
        className="rounded-xl object-cover"
      />
    )
  }
  const color = item?.profile.accentColor ?? ASSISTANT_FALLBACK_COLOR
  const name = item?.profile.name ?? agentType
  return (
    <span
      className="flex items-center justify-center rounded-xl font-semibold"
      style={{
        width: size,
        height: size,
        backgroundColor: `${color}1f`,
        border: `1px solid ${color}59`,
        color,
        fontSize: Math.round(size * 0.45),
      }}
    >
      {name.slice(0, 1)}
    </span>
  )
}
