import { SyncOutlined } from '@ant-design/icons'
import { Button, Spin, Typography } from 'antd'

import type { useCollectStockKline } from '@/hooks/useCollectStockKline'

interface KlineEmptyStateProps {
  isIntraday: boolean
  height: number
  collectKline: ReturnType<typeof useCollectStockKline>
}

/** K 线缺失态：打开页面即自动补采（见 useAutoCollectKline），失败后保留手动重试。 */
export function KlineEmptyState({ isIntraday, height, collectKline }: KlineEmptyStateProps) {
  // 仅非分时视图消费补采状态；分时缺失与 K 线补采无关，避免误显示采集动效
  const collecting = !isIntraday && collectKline.isPending
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 text-[#8c8c8c]"
      style={{ height }}
    >
      {collecting ? (
        <>
          <Spin size="small" />
          <Typography.Text type="secondary" className="text-sm">
            K 线数据缺失，正在自动补采，预计 10-30 秒...
          </Typography.Text>
        </>
      ) : (
        <>
          <Typography.Text type="secondary" className="text-sm">
            {isIntraday ? '暂无分时数据' : '暂无 K 线数据'}
          </Typography.Text>
          {!isIntraday && (
            <Button
              size="small"
              icon={<SyncOutlined />}
              onClick={() => collectKline.mutate(undefined)}
            >
              补采 K 线数据
            </Button>
          )}
        </>
      )}
      {collectKline.isError && (
        <Typography.Text type="danger" className="text-xs">
          {(collectKline.error as Error).message}
        </Typography.Text>
      )}
    </div>
  )
}
