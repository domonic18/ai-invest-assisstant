/**
 * 对话对象头像资产映射（科技风）：常规助手用助手核心头像；交易 Agent 按人设
 * 模板（promptId）取原型头像，未登记的原型回落 accentColor + 名称首字方块。
 * promptId 清单真相源 backend/app/skills/registry.py（trading-* 作业程序），
 * 新增模板需在此同步登记，否则该 Agent 回落首字方块。
 */
import agentLongLineImg from '@/assets/agent-long-line.png'
import agentM60Img from '@/assets/agent-m60.png'
import agentShortLineImg from '@/assets/agent-short-line.png'
import assistantAvatarImg from '@/assets/assistant-avatar.png'

export const ASSISTANT_AVATAR = assistantAvatarImg

/** 常规助手主色（头像描边 / 选中态状态点用）。 */
export const ASSISTANT_FALLBACK_COLOR = '#22d3ee'

/** promptId → 原型头像资产。 */
export const AGENT_PROMPT_AVATARS: Record<string, string> = {
  trading_agent_short_line: agentShortLineImg,
  trading_agent_long_line: agentLongLineImg,
  trading_agent_m60: agentM60Img,
}
