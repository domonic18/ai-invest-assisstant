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
  Table,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { useFinancial } from '@/hooks/useFinancial'

const METRIC_LABELS: Record<string, string> = {
  debt_ratio: '资产负债率',
  current_ratio: '流动比率',
  roe: '净资产收益率 (ROE)',
  gross_margin: '毛利率',
  net_margin: '净利率',
  operating_cf_ratio: '经营现金流/营收',
}

export function Financial() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const [reportDate, setReportDate] = useState<string | undefined>(undefined)

  const { data, isLoading } = useFinancial(code || '', reportDate)

  const handleDateChange = (date: Dayjs | null) => {
    setReportDate(date ? date.format('YYYY-MM-DD') : undefined)
  }

  const renderPercent = (value: number | null) =>
    value === null ? '-' : `${(value * 100).toFixed(2)}%`

  const statementColumns = [
    { title: '科目', dataIndex: 'label', key: 'label' },
    { title: '金额', dataIndex: 'value', key: 'value' },
  ]

  const buildBalanceRows = () => {
    const bs = data?.financialBalanceSheet
    if (!bs) return []
    return [
      { label: '总资产', value: bs.totalAssets },
      { label: '流动资产', value: bs.currentAssets },
      { label: '现金及等价物', value: bs.cashEquivalents },
      { label: '应收账款', value: bs.accountsReceivable },
      { label: '存货', value: bs.inventory },
      { label: '固定资产', value: bs.fixedAssets },
      { label: '无形资产', value: bs.intangibleAssets },
      { label: '商誉', value: bs.goodwill },
      { label: '总负债', value: bs.totalLiabilities },
      { label: '流动负债', value: bs.currentLiabilities },
      { label: '长期负债', value: bs.longTermDebt },
      { label: '所有者权益', value: bs.totalEquity },
    ].filter((row) => row.value !== null)
  }

  const buildIncomeRows = () => {
    const inc = data?.financialIncomeStatement
    if (!inc) return []
    return [
      { label: '营业收入', value: inc.totalRevenue },
      { label: '营业成本', value: inc.operatingCost },
      { label: '销售费用', value: inc.sellingExpense },
      { label: '管理费用', value: inc.adminExpense },
      { label: '研发费用', value: inc.researchDevelopmentExpense },
      { label: '财务费用', value: inc.financeExpense },
      { label: '营业利润', value: inc.operatingProfit },
      { label: '净利润', value: inc.netProfit },
      { label: '扣非净利润', value: inc.netProfitDeducted },
      { label: '每股收益', value: inc.eps },
    ].filter((row) => row.value !== null)
  }

  const buildCashRows = () => {
    const cf = data?.financialCashFlowStatement
    if (!cf) return []
    return [
      { label: '经营活动现金流', value: cf.cashFlowFromOperations },
      { label: '投资活动现金流', value: cf.cashFlowFromInvesting },
      { label: '筹资活动现金流', value: cf.cashFlowFromFinancing },
      { label: '净现金流', value: cf.netCashFlow },
      { label: '自由现金流', value: cf.freeCashFlow },
    ].filter((row) => row.value !== null)
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

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8}>
              <Card title="资产负债表">
                <Table
                  dataSource={buildBalanceRows()}
                  columns={statementColumns}
                  rowKey="label"
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card title="利润表">
                <Table
                  dataSource={buildIncomeRows()}
                  columns={statementColumns}
                  rowKey="label"
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card title="现金流量表">
                <Table
                  dataSource={buildCashRows()}
                  columns={statementColumns}
                  rowKey="label"
                  pagination={false}
                  size="small"
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
