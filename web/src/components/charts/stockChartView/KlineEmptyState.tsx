import { SyncOutlined } from '@ant-design/icons'
import { Button, Typography } from 'antd'

import type { useCollectStockKline } from '@/hooks/useCollectStockKline'

interface KlineEmptyStateProps {
  isIntraday: boolean
  height: number
  collectKline: ReturnType<typeof useCollectStockKline>
}

export function KlineEmptyState({ isIntraday, height, collectKline }: KlineEmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 text-[#8c8c8c]"
      style={{ height }}
    >
      <Typography.Text type="secondary" className="text-sm">
        {isIntraday ? '暂无分时数据' : '暂无 K 线数据'}
      </Typography.Text>
      {!isIntraday && (
        <>
          <Button
            size="small"
            icon={<SyncOutlined spin={collectKline.isPending} />}
            loading={collectKline.isPending}
            onClick={() => collectKline.mutate()}
          >
            {collectKline.isPending ? '采集中，预计 10-30 秒...' : '补采 K 线数据'}
          </Button>
          {collectKline.isError && (
            <Typography.Text type="danger" className="text-xs">
              {(collectKline.error as Error).message}
            </Typography.Text>
          )}
          {collectKline.isSuccess && (
            <Typography.Text type="success" className="text-xs">
              采集完成
            </Typography.Text>
          )}
        </>
      )}
    </div>
  )
}
