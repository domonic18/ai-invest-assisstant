import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Empty, Input, List, Row, Space, Spin, Statistic, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ChainGraph } from '@/components/charts/ChainGraph'
import { useChainAnalysis } from '@/hooks/useChain'
import type { ChainNode } from '@ai-invest/shared'

const EXAMPLE_INDUSTRIES = ['半导体', '新能源', '医药生物', '人工智能', '消费电子']

export function ChainAnalysis() {
  const { industry } = useParams<{ industry?: string }>()
  const [inputIndustry, setInputIndustry] = useState(industry || '半导体')
  const [selectedNode, setSelectedNode] = useState<ChainNode | null>(null)

  const { mutate, data: result, isPending, error } = useChainAnalysis()

  useEffect(() => {
    if (industry) {
      setInputIndustry(industry)
      mutate({ industry })
    }
  }, [industry, mutate])

  const handleAnalyze = () => {
    if (!inputIndustry.trim()) return
    mutate({ industry: inputIndustry.trim() })
    setSelectedNode(null)
  }

  const handleNodeClick = (nodeName: string) => {
    const node = result?.nodes.find((n) => n.name === nodeName)
    if (node) setSelectedNode(node)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Typography.Title level={4} className="!mb-0">产业链全景分析</Typography.Title>
        <Space>
          <Input
            value={inputIndustry}
            onChange={(e) => setInputIndustry(e.target.value)}
            placeholder="输入行业名称"
            prefix={<SearchOutlined />}
            onPressEnter={handleAnalyze}
            style={{ width: 240 }}
          />
          <Button type="primary" icon={<ReloadOutlined />} onClick={handleAnalyze} loading={isPending}>
            AI 分析
          </Button>
        </Space>
      </div>

      <Space wrap className="mb-4">
        {EXAMPLE_INDUSTRIES.map((item) => (
          <Button key={item} size="small" onClick={() => setInputIndustry(item)}>
            {item}
          </Button>
        ))}
      </Space>

      {error && (
        <Alert
          message="分析失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      )}

      {isPending && (
        <div className="flex justify-center py-20">
          <Spin size="large" tip="AI 正在生成产业链分析..." />
        </div>
      )}

      {!isPending && !result && !error && (
        <Empty description="点击 AI 分析生成产业链图谱" />
      )}

      {result && (
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={16}>
            <Card title="产业链关系图谱" variant="borderless">
              <ChainGraph nodes={result.nodes} edges={result.edges} onNodeClick={handleNodeClick} />
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <div className="space-y-4">
              {selectedNode ? (
                <Card title={`节点：${selectedNode.name}`} variant="borderless">
                  <Space direction="vertical" className="w-full">
                    <Statistic title="平均毛利率" value={selectedNode.avgGrossMargin} suffix="%" precision={2} />
                    <Statistic title="营收增长" value={selectedNode.revenueGrowth} suffix="%" precision={2} />
                    <Statistic title="议价能力" value={selectedNode.bargainingPower} precision={2} />
                    <Typography.Text type="secondary">代表公司：</Typography.Text>
                    <List
                      size="small"
                      dataSource={selectedNode.companies}
                      renderItem={(company) => (
                        <List.Item>{company.name} ({company.code})</List.Item>
                      )}
                    />
                  </Space>
                </Card>
              ) : (
                <Card title="节点详情" variant="borderless">
                  <Typography.Text type="secondary">点击图谱中的节点查看详情</Typography.Text>
                </Card>
              )}

              <Card title="AI 综述" variant="borderless">
                <Typography.Paragraph>{result.summary}</Typography.Paragraph>
              </Card>

              <Card title="机会" variant="borderless">
                <List
                  size="small"
                  dataSource={result.opportunities}
                  renderItem={(item) => <List.Item><Typography.Text className="text-green-400">{item}</Typography.Text></List.Item>}
                />
              </Card>

              <Card title="风险" variant="borderless">
                <List
                  size="small"
                  dataSource={result.risks}
                  renderItem={(item) => <List.Item><Typography.Text className="text-red-400">{item}</Typography.Text></List.Item>}
                />
              </Card>
            </div>
          </Col>
        </Row>
      )}
    </div>
  )
}
