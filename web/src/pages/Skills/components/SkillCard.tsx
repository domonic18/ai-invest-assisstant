import { Button, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { MouseEvent, ReactNode } from 'react'
import type { ApiSkillItem } from '@ai-invest/shared'
import {
  SKILL_KIND_BADGES,
  SKILL_SCENARIO_LABELS,
  type SkillScenario,
} from '@ai-invest/shared'

interface SkillCardProps {
  skill: ApiSkillItem
  installPending?: boolean
  uninstallPending?: boolean
  onInstall?: (skillId: string) => void
  onUninstall?: (skillId: string) => void
  footer?: ReactNode
}

/** 技能卡片：整卡可点进详情（/skills/:id），操作按钮阻止冒泡。 */
export function SkillCard({
  skill,
  installPending,
  uninstallPending,
  onInstall,
  onUninstall,
  footer,
}: SkillCardProps) {
  const navigate = useNavigate()
  const badge = SKILL_KIND_BADGES[skill.kind]

  const stop = (e: MouseEvent) => e.stopPropagation()

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/skills/${skill.skillId}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') navigate(`/skills/${skill.skillId}`)
      }}
      className="group flex h-full cursor-pointer flex-col rounded-lg border border-gray-800 bg-[#171a20] p-3 transition-colors hover:border-[#5e6ad2]/60 hover:bg-[#1a1e26]"
    >
      <div className="flex items-center justify-between gap-2">
        <Typography.Text strong ellipsis={{ tooltip: skill.label }} className="!text-sm">
          {skill.label}
        </Typography.Text>
        <span onClick={stop} className="shrink-0">
          <Tag color={skill.isBuiltin ? 'gold' : 'purple'} bordered={false} className="!mr-0">
            {skill.isBuiltin ? '官方' : '自定义'}
          </Tag>
        </span>
      </div>
      <div className="flex items-center gap-1.5 !my-1.5 flex-wrap" onClick={stop}>
        <Tag color={badge.color} bordered={false} className="!mr-0">
          {badge.label}
        </Tag>
        {skill.scenario && (
          <Tag bordered={false} className="!mr-0">
            {SKILL_SCENARIO_LABELS[skill.scenario as SkillScenario]}
          </Tag>
        )}
      </div>
      <Typography.Paragraph
        type="secondary"
        ellipsis={{ rows: 2, tooltip: skill.description ?? true }}
        className="!text-xs !mb-2 flex-1"
      >
        {skill.description ?? '暂无描述'}
      </Typography.Paragraph>
      <div className="flex items-center gap-2" onClick={stop}>
        {footer ?? (
          <>
            {skill.isBuiltin ? (
              <Tag bordered={false}>内置 · 助手直接可用</Tag>
            ) : skill.installed ? (
              <Tag color="green" bordered={false}>
                已安装
              </Tag>
            ) : (
              <Button
                size="small"
                type="primary"
                loading={installPending}
                onClick={() => onInstall?.(skill.skillId)}
              >
                安装
              </Button>
            )}
            {skill.installed && onUninstall && !skill.isBuiltin && (
              <Button
                size="small"
                loading={uninstallPending}
                onClick={() => onUninstall(skill.skillId)}
              >
                卸载
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  )
}
