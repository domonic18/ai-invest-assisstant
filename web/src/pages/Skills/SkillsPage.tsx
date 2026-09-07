import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Col, Empty, List, Row, Segmented, Spin, Tabs, Tag, Typography } from 'antd'
import { useState } from 'react'
import type { ApiSkillItem, SkillKind } from '@ai-invest/shared'

import {
  useInstallSkill,
  useSkillSquare,
  useUninstallSkill,
} from '@/hooks/useSkills'
import { SKILL_KIND_COLORS, SKILL_KIND_LABELS } from './constants'
import { SkillDetailDrawer } from './components/SkillDetailDrawer'
import { SkillFormDrawer } from './components/SkillFormDrawer'

type KindFilter = SkillKind | 'all'

const KIND_FILTER_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '可执行', value: 'executable' },
  { label: '提示词', value: 'prompt_only' },
  { label: '方法论', value: 'doc_only' },
  { label: '自定义', value: 'custom' },
]

export function SkillsPage() {
  const [detailSkillId, setDetailSkillId] = useState<string | null>(null)
  const [formTarget, setFormTarget] = useState<ApiSkillItem | 'new' | null>(null)
  const [kindFilter, setKindFilter] = useState<KindFilter>('all')

  const { data, isLoading } = useSkillSquare()
  const installSkill = useInstallSkill()
  const uninstallSkill = useUninstallSkill()

  const available = data?.available ?? []
  const mine = data?.mine ?? []
  const installed = mine.filter((skill) => skill.installed)
  const myCustom = mine.filter((skill) => !skill.isBuiltin && !skill.installed)
  const filteredAvailable =
    kindFilter === 'all' ? available : available.filter((skill) => skill.kind === kindFilter)

  const renderSkillCard = (skill: ApiSkillItem) => (
    <Col xs={24} sm={12} lg={8} key={skill.skillId}>
      <Card
        size="small"
        className="h-full"
        styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%' } }}
      >
        <div className="flex items-center justify-between gap-2">
          <Typography.Text strong ellipsis={{ tooltip: skill.label }} className="!text-sm">
            {skill.label}
          </Typography.Text>
          <Tag color={SKILL_KIND_COLORS[skill.kind]}>{SKILL_KIND_LABELS[skill.kind]}</Tag>
        </div>
        <Typography.Text code className="!text-xs !my-1 self-start">
          {skill.skillId}
        </Typography.Text>
        <Typography.Paragraph
          type="secondary"
          ellipsis={{ rows: 2, tooltip: skill.description ?? true }}
          className="!text-xs !mb-2 flex-1"
        >
          {skill.description ?? '暂无描述'}
        </Typography.Paragraph>
        <div className="flex items-center gap-2">
          <Button size="small" type="link" className="!px-0" onClick={() => setDetailSkillId(skill.skillId)}>
            详情
          </Button>
          <span style={{ flex: 1 }} />
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
              loading={installSkill.isPending && installSkill.variables === skill.skillId}
              onClick={() => installSkill.mutate(skill.skillId)}
            >
              安装
            </Button>
          )}
        </div>
      </Card>
    </Col>
  )

  const squarePane = (
    <Spin spinning={isLoading}>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <Segmented options={KIND_FILTER_OPTIONS} value={kindFilter} onChange={(v) => setKindFilter(v as KindFilter)} />
        <Typography.Text type="secondary" className="text-xs">
          内置技能全量挂载给 AI 助手，无需安装；安装语义仅对自定义技能生效
        </Typography.Text>
      </div>
      {filteredAvailable.length === 0 && !isLoading ? (
        <Empty description="暂无技能" />
      ) : (
        <Row gutter={[12, 12]}>{filteredAvailable.map(renderSkillCard)}</Row>
      )}
    </Spin>
  )

  const minePane = (
    <Spin spinning={isLoading}>
      <Typography.Title level={5} className="!mt-0">
        我的自定义技能
      </Typography.Title>
      <Typography.Text type="secondary" className="text-xs block mb-3">
        自定义技能是配置（提示词契约），不是代码；发布后对其他用户可见可安装
      </Typography.Text>
      {myCustom.length === 0 && !isLoading ? (
        <Empty description="还没有自定义技能" className="!my-6" />
      ) : (
        <Row gutter={[12, 12]}>
          {myCustom.map((skill) => (
            <Col xs={24} md={12} key={skill.skillId}>
              <Card
                size="small"
                className={skill.published ? '' : 'border-dashed'}
                styles={{ body: { display: 'flex', flexDirection: 'column', height: '100%' } }}
              >
                <div className="flex items-center justify-between gap-2">
                  <Typography.Text strong ellipsis={{ tooltip: skill.label }} className="!text-sm">
                    {skill.label}
                  </Typography.Text>
                  <span className="flex items-center gap-1">
                    {skill.published ? (
                      <Tag color="green" bordered={false}>
                        已发布
                      </Tag>
                    ) : (
                      <Tag bordered={false}>草稿</Tag>
                    )}
                    <Tag color={SKILL_KIND_COLORS.custom} bordered={false}>
                      自定义
                    </Tag>
                  </span>
                </div>
                <Typography.Text code className="!text-xs !my-1 self-start">
                  {skill.skillId}
                </Typography.Text>
                <Typography.Paragraph
                  type="secondary"
                  ellipsis={{ rows: 2, tooltip: skill.description ?? true }}
                  className="!text-xs !mb-2 flex-1"
                >
                  {skill.description ?? '暂无描述'}
                </Typography.Paragraph>
                <div className="flex items-center gap-2">
                  <Button size="small" onClick={() => setFormTarget(skill)}>
                    编辑
                  </Button>
                  <Button size="small" type="link" className="!px-0" onClick={() => setDetailSkillId(skill.skillId)}>
                    详情
                  </Button>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Typography.Title level={5} className="!mt-6">
        已安装
      </Typography.Title>
      {installed.length === 0 && !isLoading ? (
        <Empty description="尚未安装技能" className="!my-6" />
      ) : (
        <List
          size="small"
          bordered
          dataSource={installed}
          renderItem={(skill) => (
            <List.Item
              actions={[
                <Button
                  key="uninstall"
                  size="small"
                  danger
                  loading={uninstallSkill.isPending && uninstallSkill.variables === skill.skillId}
                  onClick={() => uninstallSkill.mutate(skill.skillId)}
                >
                  卸载
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <span className="flex items-center gap-2">
                    <span>{skill.label}</span>
                    <Tag color={SKILL_KIND_COLORS[skill.kind]} bordered={false}>
                      {SKILL_KIND_LABELS[skill.kind]}
                    </Tag>
                    {skill.enabled === false && <Tag bordered={false}>已停用</Tag>}
                  </span>
                }
                description={<Typography.Text code className="!text-xs">{skill.skillId}</Typography.Text>}
              />
            </List.Item>
          )}
        />
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

      <Card variant="borderless">
        <Tabs
          defaultActiveKey="square"
          items={[
            { key: 'square', label: `技能广场 (${available.length})`, children: squarePane },
            { key: 'mine', label: `我的技能 (${mine.length})`, children: minePane },
          ]}
        />
      </Card>

      <SkillDetailDrawer skillId={detailSkillId} onClose={() => setDetailSkillId(null)} />
      <SkillFormDrawer target={formTarget} onClose={() => setFormTarget(null)} />
    </div>
  )
}
