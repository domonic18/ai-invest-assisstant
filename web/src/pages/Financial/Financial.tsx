import { ArrowLeftOutlined, WalletOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Empty,
  Row,
  Space,
  Statistic,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { FINANCIAL_METRIC_LABELS } from '@/constants/financial'
import { useFinancial } from '@/hooks/useFinancial'

import { FinancialStatementTables } from './components/FinancialStatementTables'
import { renderPercent } from './utils'

const METRIC_LABELS = FINANCIAL_METRIC_LABELS

export function Financial() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const [reportDate, setReportDate] = useState<string | undefined>(undefined)

  const { data, isLoading } = useFinancial(code || '', reportDate)

  const handleDateChange = (date: Dayjs | null) => {
    setReportDate(date ? date.format('YYYY-MM-DD') : undefined)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            返回
          </Button>
          <h2 className="text-xl font-semibold">
            <WalletOutlined /> {code} 财务健康度
          </h2>
        </Space>
        <DatePicker
          placeholder="选择报告期"
          onChange={handleDateChange}
          allowClear
        />
      </div>

      {!data && !isLoading && <Empty description="暂无数据" />}

      {data && (
        <>
          <Descriptions title="报告期" className="mb-4" bordered>
            <Descriptions.Item label="报告期">{data.reportDate || '-'}</Descriptions.Item>
            <Descriptions.Item label="报告类型">{data.reportType || '-'}</Descriptions.Item>
          </Descriptions>

          <Row gutter={[16, 16]} className="mb-4">
            {Object.entries(data.metrics).map(([key, value]) => (
              <Col xs={24} sm={12} lg={8} key={key}>
                <Card>
                  <Statistic
                    title={METRIC_LABELS[key] || key}
                    value={renderPercent(value)}
                  />
                </Card>
              </Col>
            ))}
          </Row>

          <FinancialStatementTables data={data} />
        </>
      )}
    </div>
  )
}
