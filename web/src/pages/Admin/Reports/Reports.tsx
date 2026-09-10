import { Card, Col, Row, Statistic, Tabs } from 'antd'

import { useReportStorageSummary } from '@/hooks/useAdminReports'
import { formatBytes } from '@/utils/formatters'

import { FinancialReportPanel } from './FinancialReportPanel'
import { ResearchPanel } from './ResearchPanel'

const FILE_TYPE_LABELS: Record<string, string> = {
  research_report: '研报',
  financial_report: '财报',
  announcement: '公告',
}

export function AdminReports() {
  const { data: storage } = useReportStorageSummary()

  return (
    <Card title="报告管理" variant="borderless">
      {storage && (
        <Row gutter={[16, 16]} className="mb-4">
          {storage.items.map((item) => (
            <Col key={item.fileType} xs={12} sm={8} md={6}>
              <Card size="small" variant="outlined">
                <Statistic
                  title={FILE_TYPE_LABELS[item.fileType] ?? item.fileType}
                  value={formatBytes(item.sizeBytes)}
                  suffix={`${item.fileCount} 个文件`}
                />
              </Card>
            </Col>
          ))}
          <Col xs={12} sm={8} md={6}>
            <Card size="small" variant="outlined">
              <Statistic
                title="总计"
                value={formatBytes(storage.totalSizeBytes)}
                suffix={`${storage.totalFileCount} 个文件`}
              />
            </Card>
          </Col>
        </Row>
      )}
      <Tabs
        items={[
          { key: 'research', label: '研报', children: <ResearchPanel /> },
          {
            key: 'financial',
            label: '财报',
            children: <FinancialReportPanel />,
          },
        ]}
      />
    </Card>
  )
}
