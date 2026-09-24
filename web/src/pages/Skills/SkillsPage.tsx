import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Col, Empty, Input, Row, Spin, Switch, Tabs, Tag, Typography } from 'antd'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ApiSkillItem } from '@ai-invest/shared'
import { SKILL_KIND_BADGES, SKILL_SCENARIOS, SKILL_SCENARIO_LABELS } from '@ai-invest/shared'

import {
  useInstallSkill,
  useSkillSquare,
  useToggleInstallSkill,
  useUninstallSkill,
} from '@/hooks/useSkills'

import { SkillCard } from './components/SkillCard'
import { SkillFormDrawer } from './components/SkillFormDrawer'

type ScenarioFilter = 'all' | (typeof SKILL_SCENARIOS)[number]

const SCENARIO_TAB_ITEMS = [
  { key: 'all', label: '全部' },
  ...SKILL_SCENARIOS.map((s) => ({ key: s, label: SKILL_SCENARIO_LABELS[s] })),
]

function matchFilter(skill: ApiSkillItem, scenario: ScenarioFilter, keyword: string) {
  if (scenario !== 'all' && skill.scenario !== scenario) return false
  if (!keyword) return true
  const kw = keyword.toLowerCase()
  return (
    skill.label.toLowerCase().includes(kw) || skill.skillId.toLowerCase().includes(kw)
  )
}

export function SkillsPage() {
  const [formTarget, setFormTarget] = useState<ApiSkillItem | 'new' | null>(null)
  const [scenario, setScenario] = useState<ScenarioFilter>('all')
  const [keyword, setKeyword] = useState('')
  const [activeTab, setActiveTab] = useState<'square' | 'mine'>('square')
  const navigate = useNavigate()

  const { data, isLoading } = useSkillSquare()
  const installSkill = useInstallSkill()
  const uninstallSkill = useUninstallSkill()
  const toggleInstall = useToggleInstallSkill()

  const available = useMemo(() => data?.available ?? [], [data])
  const mine = useMemo(() => data?.mine ?? [], [data])
  const installed = mine.filter((skill) => skill.installed)
  const myCustom = mine.filter((skill) => !skill.isBuiltin && !skill.installed)

  const filteredAvailable = useMemo(
    () => available.filter((skill) => matchFilter(skill, scenario, keyword)),
    [available, scenario, keyword],
  )

  const renderCard = (skill: ApiSkillItem, colProps: { xs: number; sm: number; lg: number }) => (
    <Col {...colProps} key={skill.skillId}>
      <SkillCard
        skill={skill}
        installPending={installSkill.isPending && installSkill.variables === skill.skillId}
        uninstallPending={uninstallSkill.isPending && uninstallSkill.variables === skill.skillId}
        onInstall={(id) => installSkill.mutate(id)}
        onUninstall={(id) => uninstallSkill.mutate(id)}
      />
    </Col>
  )

  const squarePane = (
    <Spin spinning={isLoading}>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <Tabs
          activeKey={scenario}
          onChange={(key) => setScenario(key as ScenarioFilter)}
          items={SCENARIO_TAB_ITEMS}
          size="small"
          className="!mb-0 [&_.ant-tabs-nav]:!mb-0"
        />
        <Input
          allowClear
          prefix={<SearchOutlined className="text-gray-500" />}
          placeholder="搜索技能名称 / ID"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="w-56"
        />
      </div>
      <Typography.Text type="secondary" className="text-xs block mb-3">
        内置技能全量挂载给 AI 助手，无需安装；安装语义仅对自定义技能生效
      </Typography.Text>
      {filteredAvailable.length === 0 && !isLoading ? (
        <Empty description="没有符合条件的技能" />
      ) : (
        <Row gutter={[12, 12]}>{filteredAvailable.map((skill) => renderCard(skill, { xs: 24, sm: 12, lg: 8 }))}</Row>
      )}
    </Spin>
  )

  const minePane = (
    <Spin spinning={isLoading}>
      {mine.length === 0 && !isLoading ? (
        <Empty description="还没有属于你的技能" className="!my-10">
          <div className="flex items-center justify-center gap-2">
            <Button type="primary" onClick={() => setActiveTab('square')}>
              去技能市场看看
            </Button>
            <Button onClick={() => setFormTarget('new')}>创建自定义技能</Button>
          </div>
        </Empty>
      ) : (
        <>
          {myCustom.length > 0 && (
            <>
              <Typography.Title level={5} className="!mt-0">
                我的自定义技能
              </Typography.Title>
              <Typography.Text type="secondary" className="text-xs block mb-3">
                自定义技能是配置（提示词契约），不是代码；发布后对其他用户可见可安装
              </Typography.Text>
              <Row gutter={[12, 12]}>
                {myCustom.map((skill) => (
                  <Col xs={24} md={12} key={skill.skillId}>
                    <SkillCard
                      skill={skill}
                      footer={
                        <div className="flex items-center gap-2">
                          <Button size="small" onClick={(e) => { e.stopPropagation(); setFormTarget(skill) }}>
                            编辑
                          </Button>
                          <Tag bordered={false} className="!mr-0">
                            {skill.published ? '已发布' : '草稿'}
                          </Tag>
                        </div>
                      }
                    />
                  </Col>
                ))}
              </Row>
            </>
          )}

          {installed.length > 0 && (
            <>
              <Typography.Title level={5} className={myCustom.length > 0 ? '!mt-6' : '!mt-0'}>
                已安装
              </Typography.Title>
              <div className="flex flex-col gap-2">
          {installed.map((skill) => {
            const badge = SKILL_KIND_BADGES[skill.kind]
            return (
              <div
                key={skill.skillId}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/skills/${skill.skillId}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') navigate(`/skills/${skill.skillId}`)
                }}
                className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-800 bg-[#171a20] px-3 py-2 transition-colors hover:border-[#5e6ad2]/60"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{skill.label}</span>
                    <Tag color={badge.color} bordered={false} className="!mr-0">
                      {badge.label}
                    </Tag>
                    {skill.enabled === false && <Tag bordered={false}>已停用</Tag>}
                  </div>
                  <Typography.Text code className="!text-xs">
                    {skill.skillId}
                  </Typography.Text>
                </div>
                <span onClick={(e) => e.stopPropagation()}>
                  <Switch
                    size="small"
                    checked={skill.enabled !== false}
                    loading={toggleInstall.isPending && toggleInstall.variables?.skillId === skill.skillId}
                    onChange={(checked) =>
                      toggleInstall.mutate({ skillId: skill.skillId, enabled: checked })
                    }
                  />
                </span>
                <span onClick={(e) => e.stopPropagation()}>
                  <Button
                    size="small"
                    danger
                    loading={uninstallSkill.isPending && uninstallSkill.variables === skill.skillId}
                    onClick={() => uninstallSkill.mutate(skill.skillId)}
                  >
                    卸载
                  </Button>
                </span>
              </div>
            )
          })}
              </div>
            </>
          )}
        </>
      )}
    </Spin>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <Typography.Title level={4} className="!mb-0">
            技能广场
          </Typography.Title>
          <Typography.Text type="secondary" className="text-xs">
            浏览与安装 AI 技能；创建自定义技能（配置而非代码）
          </Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setFormTarget('new')}>
          创建自定义技能
        </Button>
      </div>

      <div className="rounded-lg border border-gray-800 bg-[#111318] p-4">
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'square' | 'mine')}
          items={[
            { key: 'square', label: `技能市场 (${available.length})`, children: squarePane },
            { key: 'mine', label: `我的技能 (${mine.length})`, children: minePane },
          ]}
        />
      </div>

      <SkillFormDrawer target={formTarget} onClose={() => setFormTarget(null)} />
    </div>
  )
}
