/**
 * 助手面板顶栏：左侧头像（管理员可点角标下拉切换对话对象）+ 标题，
 * 右侧操作按钮。关闭按钮统一为此处一个。
 * 角标为 Slack 式「挖切」圆点（描边同头部底色）；下拉为自定义面板：
 * 一级 agent 名称 + 二级 tagline 副文本，选中项以 accent 色对勾标记。
 */
import { CheckOutlined, CloseOutlined, DownOutlined, MenuOutlined, MoreOutlined } from '@ant-design/icons'
import { Button, Dropdown, Typography } from 'antd'
import { useState } from 'react'

import type { AgentOverviewItem } from '@ai-invest/shared'

import { ASSISTANT_FALLBACK_COLOR } from './ui/agentAvatars'
import { ChatAgentAvatar } from './ui/ChatAgentAvatar'

interface AssistantHeaderProps {
  title?: string | null
  onClose: () => void
  /** 当前对话对象（'assistant' 或 agent_key）：顶栏头像随之联动。 */
  agentType: string
  /** 交易 Agent 概要（头像 / tagline / accentColor）。 */
  agentItems: AgentOverviewItem[]
  /** 提供时头像带角标，点击弹下拉切换对话对象（仅管理员，面板层门控）。 */
  onSwitchAgent?: (agentType: string) => void
  /** 窄屏（移动端）下显示会话列表切换按钮：单栏布局中会话列表收进浮层 */
  showSessionsToggle?: boolean
  sessionsOpen?: boolean
  onToggleSessions?: () => void
}

interface AgentOptionView {
  key: string
  name: string
  desc: string
  color: string
}

function AgentOption({
  option,
  selected,
  agentItems,
  onSelect,
}: {
  option: AgentOptionView
  selected: boolean
  agentItems: AgentOverviewItem[]
  onSelect: (key: string) => void
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={() => onSelect(option.key)}
      className={`mx-1.5 flex w-[calc(100%-12px)] items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors ${
        selected ? 'bg-white/[0.07]' : 'hover:bg-white/[0.04]'
      }`}
    >
      <ChatAgentAvatar agentType={option.key} items={agentItems} size={36} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] leading-[18px] text-white">{option.name}</span>
        <span className="mt-0.5 block truncate text-[11px] leading-[16px] text-gray-500">
          {option.desc}
        </span>
      </span>
      {selected && (
        <CheckOutlined className="shrink-0 text-[11px]" style={{ color: option.color }} />
      )}
    </button>
  )
}

export function AssistantHeader({
  title,
  onClose,
  agentType,
  agentItems,
  onSwitchAgent,
  showSessionsToggle = false,
  sessionsOpen = false,
  onToggleSessions,
}: AssistantHeaderProps) {
  const [switchOpen, setSwitchOpen] = useState(false)

  if (!onSwitchAgent) {
    return (
      <HeaderShell
        title={title}
        onClose={onClose}
        agentType={agentType}
        agentItems={agentItems}
        showSessionsToggle={showSessionsToggle}
        sessionsOpen={sessionsOpen}
        onToggleSessions={onToggleSessions}
      />
    )
  }

  const enabled = agentItems.filter((item) => item.profile.status !== 'disabled')
  const options: AgentOptionView[] = [
    {
      key: 'assistant',
      name: '常规助手',
      desc: '通用投研问答 · 行情 / 板块 / 个股分析',
      color: ASSISTANT_FALLBACK_COLOR,
    },
    ...enabled.map((item) => ({
      key: item.profile.agentKey,
      name: item.profile.name,
      desc: item.profile.tagline || item.profile.agentKey,
      color: item.profile.accentColor ?? ASSISTANT_FALLBACK_COLOR,
    })),
  ]

  const handleSelect = (key: string) => {
    setSwitchOpen(false)
    if (key !== agentType) onSwitchAgent(key)
  }

  return (
    <HeaderShell
      title={title}
      onClose={onClose}
      agentType={agentType}
      agentItems={agentItems}
      showSessionsToggle={showSessionsToggle}
      sessionsOpen={sessionsOpen}
      onToggleSessions={onToggleSessions}
      dropdown={
        <Dropdown
          trigger={['click']}
          open={switchOpen}
          onOpenChange={setSwitchOpen}
          dropdownRender={() => (
            <div className="w-[264px] rounded-xl border border-white/10 bg-[#161a22] py-1.5 shadow-2xl">
              <div className="px-3.5 pb-1 pt-1 text-[11px] text-gray-500">切换对话对象</div>
              {options.map((option) => (
                <AgentOption
                  key={option.key}
                  option={option}
                  selected={option.key === agentType}
                  agentItems={agentItems}
                  onSelect={handleSelect}
                />
              ))}
            </div>
          )}
        >
          <button
            type="button"
            aria-label="切换对话对象"
            aria-expanded={switchOpen}
            className="group relative shrink-0 cursor-pointer"
          >
            <ChatAgentAvatar agentType={agentType} items={agentItems} size={32} />
            {/* 描边同头部底色形成挖切效果，悬停增亮提示可切换 */}
            <span className="absolute -right-1 -bottom-1 flex size-3.5 items-center justify-center rounded-full bg-[#3f4657] ring-2 ring-[#0c0e12] transition-colors group-hover:bg-[#59637a]">
              <DownOutlined style={{ fontSize: 7 }} className="text-gray-100" />
            </span>
          </button>
        </Dropdown>
      }
    />
  )
}

function HeaderShell({
  title,
  onClose,
  agentType,
  agentItems,
  showSessionsToggle,
  sessionsOpen,
  onToggleSessions,
  dropdown,
}: Omit<AssistantHeaderProps, 'onSwitchAgent'> & { dropdown?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        {showSessionsToggle && (
          <Button
            type="text"
            size="small"
            aria-label={sessionsOpen ? '收起会话列表' : '打开会话列表'}
            icon={<MenuOutlined />}
            onClick={onToggleSessions}
            className={sessionsOpen ? 'text-blue-400' : 'text-gray-400 hover:text-white'}
          />
        )}
        {dropdown ?? <ChatAgentAvatar agentType={agentType} items={agentItems} size={32} />}
        <div className="min-w-0">
          <Typography.Text className="block text-sm font-medium text-white">
            AI 投研助手
          </Typography.Text>
          {title ? (
            <Typography.Text ellipsis className="block max-w-[240px] text-xs text-gray-400">
              {title}
            </Typography.Text>
          ) : (
            <span className="text-xs text-gray-500">新会话</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <Button
          type="text"
          size="small"
          icon={<MoreOutlined />}
          className="text-gray-400 hover:text-white"
        />
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={onClose}
          className="text-gray-400 hover:text-white"
        />
      </div>
    </div>
  )
}
