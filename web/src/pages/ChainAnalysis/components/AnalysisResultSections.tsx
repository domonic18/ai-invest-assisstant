import { Card, Typography } from 'antd'

import type { ChainAnalysisResult } from '@ai-invest/shared'

import { InsightTabs } from './InsightTabs'
import { KeyCompaniesPanel } from './KeyCompaniesPanel'
import { QuadrantMatrix } from './QuadrantMatrix'
import { ValueDistributionCard } from './ValueDistributionCard'

interface AnalysisResultSectionsProps {
  result: ChainAnalysisResult
}

export function AnalysisResultSections({ result }: AnalysisResultSectionsProps) {
  const hasMatrixData = result.nodes.some(
    (node) => node.localizationRate !== null && node.avgGrossMargin !== null
  )

  const hasValueData =
    result.nodes.some((node) => node.avgGrossMargin !== null) ||
    result.valueDistribution?.highestMarginSegment != null ||
    result.valueDistribution?.lowestMarginSegment != null

  return (
    <>
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
  )
}
