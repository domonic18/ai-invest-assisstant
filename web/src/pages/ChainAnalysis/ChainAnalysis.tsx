import {
  CloseOutlined,
  MenuUnfoldOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { Alert, Button, Card, Col, Empty, Input, List, Row, Space, Spin, Tag, Typography } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ChainGraph } from '@/components/charts/ChainGraph'
import {
  useChainAnalysis,
  useChainLatest,
  useChainVersion,
  useChainVersions,
} from '@/hooks/useChain'
import { useColorScheme } from '@/stores/settings'
import { fallColorSoft, riseColorSoft } from '@/utils/formatters'
import type { ChainNode } from '@ai-invest/shared'

import { BottleneckPanel } from './components/BottleneckPanel'
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

  const latestQuery = useChainLatest(activeIndustry)
  const versionsQuery = useChainVersions(activeIndustry)
  const analyzeMutation = useChainAnalysis(activeIndustry)

  useEffect(() => {
    if (industry) {
      setInputIndustry(industry)
      setActiveIndustry(industry)
      setSelectedVersionId(null)
      setSelectedNode(null)
    }
  }, [industry])

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
    analyzeMutation.mutate(
      { industry: target },
      {
        onSuccess: (data) => {
          setSelectedVersionId(null)
          void data
        },
      }
    )
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Typography.Title level={4} className="!mb-0">
              {activeIndustry}产业链全景分析
            </Typography.Title>
            {detail && detail.version.status === 'success' && (
              <Tag color="success">
                AI 生成 · v{detail.version.versionNo} (
                {new Date(detail.version.createdAt).toLocaleDateString('zh-CN', {
                  month: '2-digit',
                  day: '2-digit',
                })}{' '}
                更新)
              </Tag>
            )}
          </div>
          {result && (
            <Typography.Text type="secondary" className="text-sm">
              覆盖 {result.nodes.length} 个产业链环节 ·{' '}
              {detail?.version.companyCount ??
                result.nodes.reduce((sum, node) => sum + node.companies.length, 0)}{' '}
              家核心标的 · {result.edges.length} 条供应关系
            </Typography.Text>
          )}
        </div>
        <Space>
          <Input
            value={inputIndustry}
            onChange={(e) => setInputIndustry(e.target.value)}
            placeholder="输入行业名称"
            prefix={<SearchOutlined />}
            onPressEnter={handleAnalyze}
            style={{ width: 240 }}
          />
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={handleAnalyze}
            loading={analyzeMutation.isPending}
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

      {analyzeMutation.isError && (
        <Alert
          message="分析失败"
          description={
            analyzeMutation.error instanceof Error
              ? analyzeMutation.error.message
              : '未知错误'
          }
          type="error"
          showIcon
        />
      )}

      {analyzeMutation.isPending && (
        <div className="flex justify-center py-20">
          <Spin size="large" tip="AI 正在生成产业链分析（约 1-2 分钟）..." />
        </div>
      )}

      {isLoading && !analyzeMutation.isPending && (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && !result && !analyzeMutation.isPending && (
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
          <Card title="产业链关系图谱" variant="borderless">
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

          <Card title="AI 综述" variant="borderless">
            <Typography.Paragraph className="!mb-0">
              {result.summary}
            </Typography.Paragraph>
          </Card>

          <Row gutter={[24, 24]}>
            <Col xs={24} lg={12}>
              <Card title="毛利率 × 国产化率矩阵" variant="borderless">
                <QuadrantMatrix nodes={result.nodes} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="价值分布" variant="borderless">
                <ValueDistributionCard
                  nodes={result.nodes}
                  valueDistribution={result.valueDistribution}
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={[24, 24]}>
            <Col xs={24} lg={12}>
              <Card title="瓶颈与卡脖子风险" variant="borderless">
                <BottleneckPanel nodes={result.nodes} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="核心标的" variant="borderless">
                <KeyCompaniesPanel companies={result.keyCompaniesSummary} />
              </Card>
            </Col>
          </Row>

          <Row gutter={[24, 24]}>
            <Col xs={24} lg={12}>
              <Card title="机会" variant="borderless">
                <List
                  size="small"
                  dataSource={result.opportunities}
                  renderItem={(item) => (
                    <List.Item>
                      <Space direction="vertical" size={2}>
                        <Space>
                          <Typography.Text className={riseColorSoft()} strong>
                            {item.title}
                          </Typography.Text>
                          {item.relatedSegment && <Tag>{item.relatedSegment}</Tag>}
                          {item.confidence && (
                            <Tag color="success">置信度 {item.confidence}</Tag>
                          )}
                        </Space>
                        {item.description && (
                          <Typography.Text type="secondary">
                            {item.description}
                          </Typography.Text>
                        )}
                      </Space>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="风险" variant="borderless">
                <List
                  size="small"
                  dataSource={result.risks}
                  renderItem={(item) => (
                    <List.Item>
                      <Space direction="vertical" size={2}>
                        <Space>
                          <Typography.Text className={fallColorSoft()} strong>
                            {item.title}
                          </Typography.Text>
                          {item.relatedSegment && <Tag>{item.relatedSegment}</Tag>}
                          {item.severity && (
                            <Tag color="error">严重度 {item.severity}</Tag>
                          )}
                        </Space>
                        {item.description && (
                          <Typography.Text type="secondary">
                            {item.description}
                          </Typography.Text>
                        )}
                      </Space>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
          </Row>
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
