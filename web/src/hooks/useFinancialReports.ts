import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'

import { collectFinancialReport, fetchFinancialReports } from '@/api/financial_report'
import { queryKeys } from '@/hooks/queryKeys'

export function useFinancialReports(stockCode: string, pageSize = 5) {
  return useQuery({
    queryKey: queryKeys.financialReports.list(stockCode, pageSize),
    queryFn: () => fetchFinancialReports({ stockCode, pageSize }),
  })
}

export function useCollectFinancialReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (stockCode: string) =>
      collectFinancialReport({ stockCode }),
    onSuccess: (result) => {
      message.success(`已发起财报采集（任务 #${result.logId}），完成后刷新查看`)
      void queryClient.invalidateQueries({ queryKey: queryKeys.financialReports.all })
    },
    onError: (error: Error) => message.error(error.message),
  })
}
