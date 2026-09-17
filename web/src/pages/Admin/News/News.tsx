import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, Spin, Switch, Tabs, Tooltip, Typography, message } from 'antd'

import { fetchFlashNewsSwitch, updateFlashNewsSwitch } from '@/api/adminNews'

import { NewsDocPanel } from './NewsDocPanel'
import { TelegraphPanel } from './TelegraphPanel'

/** 东财快讯一键开关：关闭即暂停采集任务，资讯中心同步隐去该渠道。 */
function FlashNewsSwitch() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'flash-news-switch'],
    queryFn: fetchFlashNewsSwitch,
  })

  const mutation = useMutation({
    mutationFn: updateFlashNewsSwitch,
    onSuccess: (result) => {
      queryClient.setQueryData(['admin', 'flash-news-switch'], result)
      message.success(result.enabled ? '东财快讯已开启' : '东财快讯已关闭')
    },
  })

  if (isLoading || !data) return <Spin size="small" />

  return (
    <Tooltip title="关闭后暂停东财快讯采集，资讯中心同步隐藏该渠道">
      <span className="inline-flex items-center gap-2">
        <Typography.Text type="secondary" className="text-xs">
          东财快讯采集
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
    <Card title="资讯管理" variant="borderless" extra={<FlashNewsSwitch />}>
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
