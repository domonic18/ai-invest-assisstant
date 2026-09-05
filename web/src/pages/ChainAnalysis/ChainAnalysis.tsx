import {
  CloseOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import {
  Alert,
  App,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'

import { ChainGraph } from '@/components/charts/ChainGraph'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import {
  useChainIndustries,
  useChainLatest,
  useChainVersion,
  useChainVersions,
  useDeleteChainVersion,
} from '@/hooks/useChain'
import { useAssistantStore } from '@/stores/assistant'
import { useColorScheme } from '@/stores/settings'
import { apiErrorMessage } from '@/utils/errorMessage'
import type { ChainNode } from '@ai-invest/shared'

import { ChainAlertPanel } from './components/ChainAlertPanel'
import { InsightTabs } from './components/InsightTabs'
import { KeyCompaniesPanel } from './components/KeyCompaniesPanel'
import { NodeDetailCard } from './components/NodeDetailCard'
import { QuadrantMatrix } from './components/QuadrantMatrix'
import { ValueDistributionCard } from './components/ValueDistributionCard'
import { VersionCompareDrawer } from './components/VersionCompareDrawer'
import { VersionSwitcher } from './components/VersionSwitcher'

const PRESET_INDUSTRIES = ['半导体', '新能源汽车', '光伏', '锂电池', '人工智能', '创新药']

function normalizeIndustry(industry: string): string {
  let name = industry.trim()
  const suffixes = ['产业链', '行业', '板块']
  for (const suffix of suffixes) {
    if (name.endsWith(suffix)) {
      name = name.slice(0, -suffix.length)
    }
  }
  return name.trim()
}

export function ChainAnalysis() {
  useColorScheme()
  const { industry } = useParams<{ industry?: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [activeIndustry, setActiveIndustry] = useState(industry || '半导体')
  const [selectedNode, setSelectedNode] = useState<ChainNode | null>(null)
  const [detailCollapsed, setDetailCollapsed] = useState(false)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [compareOpen, setCompareOpen] = useState(false)
  const [assistantAnalyzing, setAssistantAnalyzing] = useState(false)
  const [pendingIndustry, setPendingIndustry] = useState<string | null>(null)
  const [newAnalysisOpen, setNewAnalysisOpen] = useState(false)
  const [newIndustry, setNewIndustry] = useState('')

  const queryClient = useQueryClient()
  const sendQuestion = useAssistantStore((state) => state.sendQuestion)
  const panelOpen = useAssistantStore((s) => s.open)

  const latestQuery = useChainLatest(activeIndustry)
  const versionsQuery = useChainVersions(activeIndustry)
  const industriesQuery = useChainIndustries()
  const deleteVersionMutation = useDeleteChainVersion()

  useEffect(() => {
    if (industry) {
      setActiveIndustry(industry)
      setSelectedVersionId(null)
      setSelectedNode(null)
    }
  }, [industry])

  usePageAssistantResult('industry_chain.analysis.complete', (event) => {
    const eventIndustry = normalizeIndustry(event.industry)
    const isCurrent = eventIndustry === normalizeIndustry(activeIndustry)
    const isPending = pendingIndustry !== null && eventIndustry === normalizeIndustry(pendingIndustry)
    if (!isCurrent && !isPending) return false

    setAssistantAnalyzing(false)
    setPendingIndustry(null)
    void queryClient.invalidateQueries({ queryKey: ['chain', 'industries'] })
    if (isCurrent) {
      void queryClient.invalidateQueries({ queryKey: ['chain', 'latest', activeIndustry] })
      void queryClient.invalidateQueries({ queryKey: ['chain', 'versions', activeIndustry] })
    }
    if (isPending && !isCurrent) {
      message.success(`「${event.industry}」产业链分析已完成，可在下拉框中查看`)
    }
    return true
  })

  // 侧边栏关闭（含 agent 中途失败被放弃）时解除本页的进行中提示
  useEffect(() => {
    if (!panelOpen) {
      setAssistantAnalyzing(false)
      setPendingIndustry(null)
    }
  }, [panelOpen])

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

  const handleReanalyze = () => {
    const target = activeIndustry.trim()
    if (!target) return
    setPendingIndustry(target)
    setSelectedNode(null)
    setSelectedVersionId(null)
    setAssistantAnalyzing(true)
    sendQuestion(`请分析【${target}】产业链`)
  }

  const handleStartNewAnalysis = () => {
    const target = newIndustry.trim()
    if (!target) {
      message.warning('请输入产业链名称')
      return
    }
    setPendingIndustry(target)
    setNewAnalysisOpen(false)
    setNewIndustry('')
    setSelectedNode(null)
    setSelectedVersionId(null)
    setAssistantAnalyzing(true)
    sendQuestion(`请分析【${target}】产业链`)
  }

  const handleIndustryChange = (value: string) => {
    if (!value || normalizeIndustry(value) === normalizeIndustry(activeIndustry)) return
    navigate(`/chain/${encodeURIComponent(value)}`)
  }

  const analyzedIndustries = useMemo(() => industriesQuery.data ?? [], [industriesQuery.data])
  const industryOptions = useMemo(
    () =>
      analyzedIndustries.map((item) => ({
        value: item,
        label: item,
      })),
    [analyzedIndustries]
  )

  const handleNodeClick = (nodeName: string) => {
    const node = result?.nodes.find((item) => item.name === nodeName)
    if (node) {
      setSelectedNode(node)
      setDetailCollapsed(false)
    }
  }

  const handleDeleteVersion = (versionId: number) => {
    deleteVersionMutation.mutate(versionId, {
      onSuccess: () => {
        message.success('版本已删除')
        // 当前展示版本被删时回退到最新成功版本（selectedVersionId 置 null 即取 latest）
        if (detail?.version.id === versionId) {
          setSelectedVersionId(null)
          setSelectedNode(null)
        }
      },
      onError: (err) => message.error(apiErrorMessage(err, '删除失败，请稍后重试')),
    })
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
      <div className="flex items-center justify-between gap-4 flex-wrap">
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
        <Space wrap>
          <Select
            value={activeIndustry}
            onChange={handleIndustryChange}
            options={industryOptions}
            loading={industriesQuery.isLoading}
            placeholder="选择已分析产业链"
            showSearch
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
            style={{ minWidth: 180 }}
          />
          <Tooltip title="使用 AI 助手重新分析当前产业链">
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={handleReanalyze}
              loading={assistantAnalyzing}
            >
              重新分析
            </Button>
          </Tooltip>
          <Button icon={<PlusOutlined />} onClick={() => setNewAnalysisOpen(true)}>
            新建分析
          </Button>
        </Space>
      </div>

      <Modal
        title="分析新产业链"
        open={newAnalysisOpen}
        onOk={handleStartNewAnalysis}
        onCancel={() => setNewAnalysisOpen(false)}
        okButtonProps={{ icon: <RobotOutlined />, loading: assistantAnalyzing }}
        okText="开始 AI 分析"
        cancelText="取消"
      >
        <div className="space-y-4">
          <Input
            value={newIndustry}
            onChange={(e) => setNewIndustry(e.target.value)}
            placeholder="输入产业链名称，如：机器人、创新药"
            onPressEnter={handleStartNewAnalysis}
          />
          <div className="flex items-center gap-2 flex-wrap">
            <Typography.Text type="secondary" className="text-xs whitespace-nowrap">
              快速选择：
            </Typography.Text>
            <Space size={4} wrap>
              {PRESET_INDUSTRIES.map((item) => (
                <Tag
                  key={item}
                  className="cursor-pointer hover:border-[#6366f1] hover:text-[#6366f1] transition-colors"
                  onClick={() => setNewIndustry(item)}
                >
                  {item}
                </Tag>
              ))}
            </Space>
          </div>
        </div>
      </Modal>

      <ChainAlertPanel industry={activeIndustry} />

      {versions.length > 0 && (
        <VersionSwitcher
          versions={versions}
          currentVersionId={detail?.version.id ?? null}
          onChange={(id) => {
            setSelectedVersionId(id)
            setSelectedNode(null)
          }}
          onCompare={() => setCompareOpen(true)}
          onDelete={handleDeleteVersion}
          deletingId={
            deleteVersionMutation.isPending
              ? (deleteVersionMutation.variables ?? null)
              : null
          }
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
