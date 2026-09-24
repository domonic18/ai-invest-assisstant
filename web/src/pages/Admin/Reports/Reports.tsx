import { ClearOutlined } from '@ant-design/icons'
import { App, Button, Card, Col, Row, Statistic, Tabs } from 'antd'

import { useCleanupOldReports, useReportStorageSummary } from '@/hooks/useAdminReports'
import { apiErrorMessage } from '@/utils/errorMessage'
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
  const cleanupMutation = useCleanupOldReports()
  const { message, modal } = App.useApp()

  const confirmCleanup = () => {
    modal.confirm({
      title: '清理 3 个月前的报告文件',
      content:
        '将永久删除创建时间超过 3 个月的研报 PDF 及其存储对象，释放空间且不可恢复。确定继续吗？',
      okText: '清理',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          const result = await cleanupMutation.mutateAsync()
          message.success(
            `已清理 ${result.removedCount} 个文件，释放 ${formatBytes(result.sizeBytes)}`,
          )
        } catch (err) {
          message.error(apiErrorMessage(err, '清理失败'))
        }
      },
    })
  }

  return (
    <Card
      title="报告管理"
      variant="borderless"
      extra={
        <Button
          danger
          icon={<ClearOutlined />}
          loading={cleanupMutation.isPending}
          onClick={confirmCleanup}
        >
          清理 3 个月前报告
        </Button>
      }
    >
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
