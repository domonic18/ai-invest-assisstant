import { Card, Table } from 'antd'

import type { FinancialHealth } from '@ai-invest/shared'
import { buildBalanceRows, buildCashRows, buildIncomeRows, statementColumns } from '../utils'

interface FinancialStatementTablesProps {
  data: FinancialHealth
}

export function FinancialStatementTables({ data }: FinancialStatementTablesProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Card title="资产负债表">
        <Table
          dataSource={buildBalanceRows(data)}
          columns={statementColumns}
          rowKey="label"
          pagination={false}
          size="small"
        />
      </Card>
      <Card title="利润表">
        <Table
          dataSource={buildIncomeRows(data)}
          columns={statementColumns}
          rowKey="label"
          pagination={false}
          size="small"
        />
      </Card>
      <Card title="现金流量表">
        <Table
          dataSource={buildCashRows(data)}
          columns={statementColumns}
          rowKey="label"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
