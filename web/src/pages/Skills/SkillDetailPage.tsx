import { Button, Breadcrumb, Card, Descriptions, Result, Skeleton, Space, Tag, Typography } from 'antd'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { SKILL_KIND_BADGES, SKILL_SCENARIO_LABELS } from '@ai-invest/shared'

import type { ApiSkillResponse } from '@ai-invest/shared'

import { useAuthStore } from '@/stores/auth'
import {
  useInstallSkill,
  usePublishCustomSkill,
  useSkillDetail,
  useSkillSquare,
  useUninstallSkill,
} from '@/hooks/useSkills'
import { formatDateTime } from '@/utils/formatters'

import { SkillFileBrowser } from './components/SkillFileBrowser'
import { SkillFormDrawer } from './components/SkillFormDrawer'

function Badges({ skill }: { skill: ApiSkillResponse }) {
  const badge = SKILL_KIND_BADGES[skill.kind]
  return (
    <Space size={4} wrap>
      <Tag color={badge.color} bordered={false}>
        {badge.label}
      </Tag>
      {skill.scenario && <Tag bordered={false}>{SKILL_SCENARIO_LABELS[skill.scenario]}</Tag>}
      <Tag color={skill.isBuiltin ? 'gold' : 'purple'} bordered={false}>
        {skill.isBuiltin ? '官方' : '自定义'}
      </Tag>
    </Space>
  )
}

/** 技能详情全页面（/skills/:skillId）：元信息 + 技能包文件浏览。 */
export function SkillDetailPage() {
  const { skillId = '' } = useParams()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const { data: skill, isLoading, isError } = useSkillDetail(skillId || null)
  const { data: square } = useSkillSquare()

  const installSkill = useInstallSkill()
  const uninstallSkill = useUninstallSkill()
  const publishSkill = usePublishCustomSkill()
  const [editing, setEditing] = useState(false)

  if (isError) {
    return (
      <Result
        status="404"
        title="技能不存在或不可见"
        extra={
          <Button type="primary" onClick={() => navigate('/skills')}>
            返回技能广场
          </Button>
        }
      />
    )
  }

  const squareItem = square
    ? [...(square.available ?? []), ...(square.mine ?? [])].find(
        (item) => item.skillId === skillId,
      )
    : undefined
  const isOwnCustom =
    skill != null && !skill.isBuiltin && String(skill.ownerUserId) === user?.id

  return (
    <div className="flex h-full flex-col gap-3">
      <Breadcrumb
        items={[
          { title: <a onClick={() => navigate('/skills')}>技能广场</a> },
          { title: skill?.label ?? skillId },
        ]}
      />

      <Card variant="borderless">
        {isLoading || !skill ? (
          <Skeleton active title paragraph={{ rows: 2 }} />
        ) : (
          <>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Typography.Title level={4} className="!mb-0 !mt-0">
                    {skill.label}
                  </Typography.Title>
                  <Badges skill={skill} />
                </div>
                <Typography.Text code className="!text-xs">
                  {skill.skillId}
                </Typography.Text>
                {skill.description && (
                  <Typography.Paragraph type="secondary" className="!mb-0 !mt-2 !text-xs">
                    {skill.description}
                  </Typography.Paragraph>
                )}
              </div>
              <Space wrap>
                {skill.isBuiltin ? (
                  <Tag bordered={false}>内置 · 助手直接可用</Tag>
                ) : (
                  <>
                    {isOwnCustom && (
                      <>
                        <Button onClick={() => setEditing(true)}>编辑</Button>
                        {!skill.published && (
                          <Button
                            loading={publishSkill.isPending}
                            onClick={() => publishSkill.mutate(skill.skillId)}
                          >
                            发布
                          </Button>
                        )}
                      </>
                    )}
                    {squareItem?.installed ? (
                      <Button
                        danger
                        loading={uninstallSkill.isPending}
                        onClick={() => uninstallSkill.mutate(skill.skillId)}
                      >
                        卸载
                      </Button>
                    ) : (
                      <Button
                        type="primary"
                        loading={installSkill.isPending}
                        onClick={() => installSkill.mutate(skill.skillId)}
                      >
                        安装
                      </Button>
                    )}
                  </>
                )}
              </Space>
            </div>
            <Descriptions
              className="!mt-3"
              column={{ xs: 1, sm: 2, md: 4 }}
              size="small"
              items={[
                { key: 'version', label: '版本', children: `v${skill.version}` },
                {
                  key: 'source',
                  label: '来源',
                  children: skill.isBuiltin ? '内置（随镜像分发）' : '用户自定义',
                },
                { key: 'status', label: '状态', children: skill.published ? '已发布' : '草稿' },
                {
                  key: 'updatedAt',
                  label: '更新时间',
                  children: formatDateTime(skill.updatedAt),
                },
              ]}
            />
          </>
        )}
      </Card>

      <Card
        variant="borderless"
        className="flex min-h-0 flex-1 flex-col [&>.ant-card-body]:flex [&>.ant-card-body]:flex-1 [&>.ant-card-body]:flex-col [&>.ant-card-body]:min-h-0 [&>.ant-card-body]:p-0"
      >
        <SkillFileBrowser skillId={skillId} />
      </Card>

      <SkillFormDrawer
        target={editing && skill ? { skillId: skill.skillId } : null}
        onClose={() => setEditing(false)}
      />
    </div>
  )
}
