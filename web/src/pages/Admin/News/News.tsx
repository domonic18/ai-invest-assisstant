import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, Spin, Switch, Tabs, Tooltip, Typography, message } from 'antd'

import { fetchFlashNewsDisplay, updateFlashNewsDisplay } from '@/api/adminNews'

import { NewsDocPanel } from './NewsDocPanel'
import { TelegraphPanel } from './TelegraphPanel'

/** 东财快讯展示开关：仅控制资讯中心是否展示该渠道；采集启停在「采集管理」。 */
function FlashNewsDisplay() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'flash-news-display'],
    queryFn: fetchFlashNewsDisplay,
  })

  const mutation = useMutation({
    mutationFn: updateFlashNewsDisplay,
    onSuccess: (result) => {
      queryClient.setQueryData(['admin', 'flash-news-display'], result)
      message.success(result.enabled ? '东财快讯已展示' : '东财快讯已隐藏')
    },
  })

  if (isLoading || !data) return <Spin size="small" />

  return (
    <Tooltip title="仅控制资讯中心是否展示「东财快讯」渠道；采集任务的启停请在「采集管理」中配置">
      <span className="inline-flex items-center gap-2">
        <Typography.Text type="secondary" className="text-xs">
          显示东财快讯
        </Typography.Text>
        <Switch
          checked={data.enabled}
          loading={mutation.isPending}
          onChange={(checked) => mutation.mutate(checked)}
        />
      </span>
    </Tooltip>
  )
}

export function AdminNews() {
  return (
    <Card title="资讯管理" variant="borderless" extra={<FlashNewsDisplay />}>
      <Tabs
        items={[
          { key: 'telegraph', label: '电报', children: <TelegraphPanel /> },
          { key: 'news', label: '快讯', children: <NewsDocPanel docType="news" /> },
          {
            key: 'announcement',
            label: '公告',
            children: <NewsDocPanel docType="announcement" />,
          },
        ]}
      />
    </Card>
  )
}
