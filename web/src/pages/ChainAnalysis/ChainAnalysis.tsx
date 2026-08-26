import {
  CloseOutlined,
  MenuUnfoldOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { Alert, Button, Card, Empty, Input, Space, Spin, Tag, Typography } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { ChainGraph } from '@/components/charts/ChainGraph'
import {
  useChainLatest,
  useChainVersion,
  useChainVersions,
} from '@/hooks/useChain'
import { useAssistantStore } from '@/stores/assistant'
import { useColorScheme } from '@/stores/settings'
import type { ChainNode } from '@ai-invest/shared'

import { InsightTabs } from './components/InsightTabs'
import { KeyCompaniesPanel } from './components/KeyCompaniesPanel'
import { NodeDetailCard } from './components/NodeDetailCard'
import { QuadrantMatrix } from './components/QuadrantMatrix'
import { ValueDistributionCard } from './components/ValueDistributionCard'
import { VersionCompareDrawer } from './components/VersionCompareDrawer'
import { VersionSwitcher } from './components/VersionSwitcher'

export function ChainAnalysis() {
  useColorScheme()
  const { industry } = useParams<{ industry?: string }>()
  const [inputIndustry, setInputIndustry] = useState(industry || '半导体')
  const [activeIndustry, setActiveIndustry] = useState(industry || '半导体')
  const [selectedNode, setSelectedNode] = useState<ChainNode | null>(null)
  const [detailCollapsed, setDetailCollapsed] = useState(false)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [compareOpen, setCompareOpen] = useState(false)
  const [assistantAnalyzing, setAssistantAnalyzing] = useState(false)

  const queryClient = useQueryClient()
  const sendQuestion = useAssistantStore((state) => state.sendQuestion)
  const pageResult = useAssistantStore((state) => state.pageResult)

  const latestQuery = useChainLatest(activeIndustry)
  const versionsQuery = useChainVersions(activeIndustry)

  useEffect(() => {
    if (industry) {
      setInputIndustry(industry)
      setActiveIndustry(industry)
      setSelectedVersionId(null)
      setSelectedNode(null)
    }
  }, [industry])

  useEffect(() => {
    if (
      pageResult?.type === 'industry_chain.analysis_complete' &&
      pageResult.industry === activeIndustry
    ) {
      setAssistantAnalyzing(false)
      void queryClient.invalidateQueries({ queryKey: ['chain', 'latest', activeIndustry] })
      void queryClient.invalidateQueries({ queryKey: ['chain', 'versions', activeIndustry] })
      useAssistantStore.getState().setPageResult(null)
    }
  }, [pageResult, activeIndustry, queryClient])

  const latestVersionId = latestQuery.data?.version.id ?? null
  const isLatestSelected =
    selectedVersionId === null || selectedVersionId === latestVersionId
  const selectedQuery = useChainVersion(
    isLatestSelected ? null : selectedVersionId
  )
  const detail = isLatestSelected ? latestQuery.data : selectedQuery.data
  const result = detail?.result ?? null
  const versions = versionsQuery.data ?? []

  const noVersionYet =
    latestQuery.error instanceof AxiosError &&
    latestQuery.error.response?.status === 404

  const handleAnalyze = () => {
    const target = inputIndustry.trim()
    if (!target) return
    setActiveIndustry(target)
    setSelectedNode(null)
    setSelectedVersionId(null)
    setAssistantAnalyzing(true)
    sendQuestion(`请分析【${target}】产业链`)
  }

  const handleNodeClick = (nodeName: string) => {
    const node = result?.nodes.find((item) => item.name === nodeName)
    if (node) {
      setSelectedNode(node)
      setDetailCollapsed(false)
    }
  }

  const isLoading =
    latestQuery.isLoading || (!isLatestSelected && selectedQuery.isLoading)

  const hasMatrixData =
    result?.nodes.some(
      (node) => node.localizationRate !== null && node.avgGrossMargin !== null
    ) ?? false

  const hasValueData =
    result?.nodes.some((node) => node.avgGrossMargin !== null) ||
    result?.valueDistribution?.highestMarginSegment != null ||
    result?.valueDistribution?.lowestMarginSegment != null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Typography.Title level={5} className="!mb-0">
            {activeIndustry}产业链
          </Typography.Title>
          {detail && detail.version.status === 'success' && (
            <Tag color="success" className="text-xs">
              AI 生成 · v{detail.version.versionNo} (
              {new Date(detail.version.createdAt).toLocaleDateString('zh-CN', {
                month: '2-digit',
                day: '2-digit',
              })}
              )
            </Tag>
          )}
        </div>
        <Space>
          <Input
            value={inputIndustry}
            onChange={(e) => setInputIndustry(e.target.value)}
            placeholder="输入行业名称"
            prefix={<SearchOutlined />}
            onPressEnter={handleAnalyze}
            style={{ width: 220 }}
          />
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={handleAnalyze}
            loading={assistantAnalyzing}
          >
            刷新分析
          </Button>
        </Space>
      </div>

      {versions.length > 0 && (
        <VersionSwitcher
          versions={versions}
          currentVersionId={detail?.version.id ?? null}
          onChange={(id) => {
            setSelectedVersionId(id)
            setSelectedNode(null)
          }}
          onCompare={() => setCompareOpen(true)}
        />
      )}

      {assistantAnalyzing && (
        <Alert
          message="AI 助手正在分析产业链"
          description="已打开 AI 助手侧边栏，可在侧边栏查看 Agent 读取资料、调用工具与思考的完整过程。"
          type="info"
          showIcon
        />
      )}

      {isLoading && !assistantAnalyzing && (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && !result && !assistantAnalyzing && (
        <Empty
          description={
            noVersionYet
              ? `「${activeIndustry}」暂无分析版本，点击 AI 分析生成`
              : '点击 AI 分析生成产业链图谱'
          }
        />
      )}

      {result && (
        <>
          <Card variant="borderless" bodyStyle={{ padding: 0 }} className="overflow-hidden">
            <div className="relative">
              <ChainGraph
                nodes={result.nodes}
                edges={result.edges}
                onNodeClick={handleNodeClick}
              />
              {selectedNode && detailCollapsed && (
                <Button
                  size="small"
                  icon={<MenuUnfoldOutlined />}
                  onClick={() => setDetailCollapsed(false)}
                  className="!absolute right-12 top-3 z-10"
                >
                  节点详情
                </Button>
              )}
              {selectedNode && !detailCollapsed && (
                <Card
                  size="small"
                  title={selectedNode.name}
                  className="!absolute right-12 top-3 bottom-3 w-80 z-10 shadow-xl flex flex-col [&_.ant-card-body]:flex-1 [&_.ant-card-body]:overflow-y-auto"
                  extra={
                    <Space size={4}>
                      <Button
                        type="text"
                        size="small"
                        icon={<MenuUnfoldOutlined rotate={180} />}
                        title="收起"
                        onClick={() => setDetailCollapsed(true)}
                      />
                      <Button
                        type="text"
                        size="small"
                        icon={<CloseOutlined />}
                        title="关闭"
                        onClick={() => setSelectedNode(null)}
                      />
                    </Space>
                  }
                >
                  <NodeDetailCard node={selectedNode} />
                </Card>
              )}
            </div>
          </Card>

          {result.summary && (
            <Card title="AI 综述" variant="borderless">
              <Typography.Paragraph className="!mb-0">
                {result.summary}
              </Typography.Paragraph>
            </Card>
          )}

          {(hasMatrixData || hasValueData) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
              {hasMatrixData && (
                <Card title="毛利率 × 国产化率矩阵" variant="borderless">
                  <QuadrantMatrix nodes={result.nodes} />
                </Card>
              )}
              {hasValueData && (
                <Card title="价值分布" variant="borderless">
                  <ValueDistributionCard
                    nodes={result.nodes}
                    valueDistribution={result.valueDistribution}
                  />
                </Card>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 md:gap-6">
            <div className="xl:col-span-2">
              <Card title="洞察分析" variant="borderless" className="h-full">
                <InsightTabs
                  opportunities={result.opportunities}
                  risks={result.risks}
                  nodes={result.nodes}
                />
              </Card>
            </div>
            <div>
              <Card title="核心标的" variant="borderless" className="h-full">
                <KeyCompaniesPanel companies={result.keyCompaniesSummary} />
              </Card>
            </div>
          </div>
        </>
      )}

      <VersionCompareDrawer
        open={compareOpen}
        versions={versions}
        defaultBaseId={
          versions.filter((v) => v.status === 'success')[1]?.id ?? null
        }
        defaultTargetId={latestVersionId}
        onClose={() => setCompareOpen(false)}
      />
    </div>
  )
}
