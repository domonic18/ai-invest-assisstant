import { Card, Tabs } from 'antd'

import { FinancialReportPanel } from './FinancialReportPanel'
import { ResearchPanel } from './ResearchPanel'

export function AdminReports() {
  return (
    <Card title="报告管理" variant="borderless">
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
