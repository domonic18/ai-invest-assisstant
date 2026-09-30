/**
 * 对话对象头像切换器（侧边栏顶部）：常规助手 = 猫头鹰圆头像，交易 Agent =
 * accentColor 芯片方块 + 名称首字。选中态 = 同色描边 + 右下角状态点，
 * 悬停 Tooltip 报全名；仅管理员可见（面板层门控）。
 */
import { Tooltip } from 'antd'

import type { AgentOverviewItem } from '@ai-invest/shared'

import owlImg from '@/assets/assistant-owl.png'

const ASSISTANT_FALLBACK_COLOR = '#22d3ee'

function AvatarButton({
  active,
  label,
  color,
  onClick,
  children,
}: {
  active: boolean
  label: string
  color: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Tooltip title={label}>
      <button
        type="button"
        aria-label={active ? `${label}（当前对话）` : `切换到 ${label}`}
        aria-pressed={active}
        onClick={onClick}
        className="relative rounded-xl transition-transform hover:scale-105"
        style={{ boxShadow: active ? `0 0 0 2px ${color}` : '0 0 0 1px rgba(255,255,255,.14)' }}
      >
        {children}
        {active && (
          <span
            className="absolute -right-1 -bottom-1 size-2.5 rounded-full border-2 border-[#111318]"
            style={{ backgroundColor: color }}
          />
        )}
      </button>
    </Tooltip>
  )
}

export function AgentAvatarSwitcher({
  current,
  items,
  onChange,
}: {
  /** 当前对话对象：'assistant' 或 agent_key */
  current: string
  items: AgentOverviewItem[]
  onChange: (agentType: string) => void
}) {
  return (
    <div>
      <div className="mb-1.5 px-0.5 text-[11px] text-gray-500">对话对象</div>
      <div className="flex flex-wrap items-center gap-2.5 pb-1">
        <AvatarButton
          active={current === 'assistant'}
          label="常规助手"
          color={ASSISTANT_FALLBACK_COLOR}
          onClick={() => onChange('assistant')}
        >
          <img src={owlImg} alt="" draggable={false} className="h-9 w-9 rounded-xl object-cover" />
        </AvatarButton>
        {items
          .filter((item) => item.profile.status !== 'disabled')
          .map((item) => {
            const color = item.profile.accentColor ?? ASSISTANT_FALLBACK_COLOR
            return (
              <AvatarButton
                key={item.profile.agentKey}
                active={current === item.profile.agentKey}
                label={item.profile.name}
                color={color}
                onClick={() => onChange(item.profile.agentKey)}
              >
                <span
                  className="flex h-9 w-9 items-center justify-center rounded-xl text-[15px] font-semibold"
                  style={{ backgroundColor: `${color}1f`, border: `1px solid ${color}59`, color }}
                >
                  {item.profile.name.slice(0, 1)}
                </span>
              </AvatarButton>
            )
          })}
      </div>
    </div>
  )
}
