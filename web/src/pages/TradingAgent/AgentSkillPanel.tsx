/**
 * 作业技能面板（D30）：trading 专属/共享技能包文件浏览 + 方法论知识源轮廓。
 * trading 技能不进技能广场，此处直读镜像目录可视化；方法论区展示 KB 绑定的
 * 章节大纲 + 纪律 + 知识卡片（计划 prompt 注入的静态层即来自同一知识源）。
 */
import { Alert, Card, Collapse, Skeleton, Tag, Typography } from 'antd'

import type { ApiAgentMethodologyView } from '@ai-invest/shared'

import { SkillFileBrowserView } from '@/pages/Skills/components/SkillFileBrowser'
import { useTradingAgentSkillFiles } from '@/hooks/useTradingAgent'

import { useAgentKey } from './agentKeyContext'

const POINT_TYPE_LABELS: Record<string, string> = {
  method: '方法',
  theorem: '定理',
  concept: '概念',
  case: '案例',
}

function MethodologySection({ methodology }: { methodology: ApiAgentMethodologyView }) {
  const pointGroups = Object.entries(
    methodology.points.reduce<Record<string, typeof methodology.points>>((acc, point) => {
      const list = acc[point.pointType] ?? []
      list.push(point)
      acc[point.pointType] = list
      return acc
    }, {}),
  )

  return (
    <div className="mt-3 border-t border-white/10 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <Typography.Text strong className="text-xs">
          方法论基座
        </Typography.Text>
        <Tag color="purple" className="!mr-0">
          {methodology.sourceName}
        </Tag>
        <Typography.Text type="secondary" className="text-xs">
          计划/会话 prompt 注入的知识源（章节总纲 + 硬纪律全量）
        </Typography.Text>
      </div>
      {methodology.outline ? (
        <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-white/10 bg-black/30 p-3 text-xs leading-relaxed whitespace-pre-wrap text-white/80">
          {methodology.outline}
        </pre>
      ) : null}
      {methodology.disciplines.length > 0 || pointGroups.length > 0 ? (
        <Collapse
          size="small"
          className="mt-2 [&_.ant-collapse-content]:bg-white/[0.02]"
          items={[
            ...(methodology.disciplines.length > 0
              ? [
                  {
                    key: 'disciplines',
                    label: `硬纪律（${methodology.disciplines.length}）`,
                    children: (
                      <ul className="space-y-2">
                        {methodology.disciplines.map((item) => (
                          <li key={item.title}>
                            <Typography.Text className="text-xs" strong>
                              {item.title}
                            </Typography.Text>
                            <Typography.Paragraph
                              type="secondary"
                              className="!mb-0 text-xs whitespace-pre-wrap"
                            >
                              {item.body}
                            </Typography.Paragraph>
                          </li>
                        ))}
                      </ul>
                    ),
                  },
                ]
              : []),
            ...pointGroups.map(([pointType, points]) => ({
              key: pointType,
              label: `${POINT_TYPE_LABELS[pointType] ?? pointType}（${points.length}）`,
              children: (
                <ul className="space-y-2">
                  {points.map((point) => (
                    <li key={point.title}>
                      <Typography.Text className="text-xs" strong>
                        {point.title}
                      </Typography.Text>
                      <Typography.Paragraph
                        type="secondary"
                        className="!mb-0 text-xs whitespace-pre-wrap"
                      >
                        {point.body}
                      </Typography.Paragraph>
                    </li>
                  ))}
                </ul>
              ),
            })),
          ]}
        />
      ) : null}
    </div>
  )
}

export function AgentSkillPanel() {
  const agentKey = useAgentKey()
  const filesQ = useTradingAgentSkillFiles(agentKey)
  const data = filesQ.data

  return (
    <Card size="small" title="作业技能">
      {filesQ.isLoading || !data ? (
        <div className="flex justify-center py-6">
          <Skeleton active title={false} paragraph={{ rows: 4 }} />
        </div>
      ) : (
        <>
          {data.skillIsSharedDefault ? (
            <Alert
              type="warning"
              showIcon
              className="!mb-3"
              message={`当前使用共享技能包 ${data.skillId}（未创建专属技能包）；专属包生成后按 agentKey 自动装载。`}
            />
          ) : null}
          <div className="flex h-[360px] flex-col overflow-hidden rounded-lg border border-white/10">
            <SkillFileBrowserView
              rootLabel={data.skillId}
              files={data.files}
              isLoading={filesQ.isLoading}
              isError={filesQ.isError}
            />
          </div>
          {data.methodology ? (
            <MethodologySection methodology={data.methodology} />
          ) : (
            <Typography.Text type="secondary" className="mt-3 block text-xs">
              未绑定方法论知识源（配置「方法论知识源」后，计划与会话将注入该 KB 的总纲与硬纪律）
            </Typography.Text>
          )}
        </>
      )}
    </Card>
  )
}
