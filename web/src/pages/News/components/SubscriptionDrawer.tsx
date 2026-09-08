import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Button,
  Drawer,
  Empty,
  Input,
  List,
  Popconfirm,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import { useState } from 'react'

import {
  useCreateNewsSubscription,
  useDeleteNewsSubscription,
  useNewsSubscriptions,
  useUpdateNewsSubscription,
} from '@/hooks/useNewsSubscriptions'
import { formatRelativeTime } from '@/utils/formatters'

interface SubscriptionDrawerProps {
  open: boolean
  onClose: () => void
}

/** 我的订阅抽屉：关键词 CRUD + 启停开关 + 命中统计。 */
export function SubscriptionDrawer({ open, onClose }: SubscriptionDrawerProps) {
  const [keyword, setKeyword] = useState('')
  const [messageApi, contextHolder] = message.useMessage()
  const { data, isLoading } = useNewsSubscriptions()
  const createSub = useCreateNewsSubscription()
  const updateSub = useUpdateNewsSubscription()
  const deleteSub = useDeleteNewsSubscription()

  const submit = () => {
    const trimmed = keyword.trim()
    if (!trimmed) return
    createSub.mutate(
      { keyword: trimmed },
      {
        onSuccess: () => {
          setKeyword('')
          messageApi.success(`已订阅「${trimmed}」，命中将在电报流中标 ★`)
        },
        onError: () => messageApi.error('订阅失败：关键词可能已存在'),
      },
    )
  }

  return (
    <Drawer
      title="我的订阅"
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
    >
      {contextHolder}
      <div className="space-y-4">
        <div>
          <Typography.Paragraph type="secondary" className="!mb-2 !text-xs">
            订阅关键词后，命中的电报会在资讯流中标注 ★，可一键筛选仅看命中。
          </Typography.Paragraph>
          <Input.Search
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={submit}
            enterButton={
              <Button type="primary" icon={<PlusOutlined />} loading={createSub.isPending}>
                订阅
              </Button>
            }
            placeholder="输入关键词，如：存储芯片 / 降准 / 新能源"
            maxLength={50}
          />
        </div>

        <Spin spinning={isLoading}>
          {(data?.length ?? 0) === 0 && !isLoading ? (
            <Empty description="暂无订阅" />
          ) : (
            <List
              dataSource={data ?? []}
              renderItem={(sub) => (
                <List.Item
                  actions={[
                    <Popconfirm
                      key="delete"
                      title="删除该订阅？"
                      description="关联命中记录将一并删除"
                      onConfirm={() => deleteSub.mutate(sub.id)}
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                      />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <span className={sub.enabled ? '' : 'opacity-50 line-through'}>
                        {sub.keyword}
                      </span>
                    }
                    description={
                      <span className="text-xs">
                        命中 {sub.hitCount} 条
                        {sub.lastHitAt && ` · 最近 ${formatRelativeTime(sub.lastHitAt)}`}
                      </span>
                    }
                  />
                  <div className="flex items-center gap-3">
                    <Tooltip title={sub.enabled ? '停用后不再扫描命中' : '启用扫描'}>
                      <Switch
                        size="small"
                        checked={sub.enabled}
                        loading={
                          updateSub.isPending && updateSub.variables?.id === sub.id
                        }
                        onChange={(enabled) =>
                          updateSub.mutate({ id: sub.id, data: { enabled } })
                        }
                      />
                    </Tooltip>
                    <Tooltip title="推送通道即将上线">
                      <Switch
                        size="small"
                        checked={sub.pushEnabled}
                        disabled
                        checkedChildren="推送"
                      />
                    </Tooltip>
                  </div>
                </List.Item>
              )}
            />
          )}
        </Spin>

        <Typography.Paragraph type="secondary" className="!text-xs">
          <Tag className="!m-0">说明</Tag>
          命中扫描每 10 分钟运行一次；推送通道上线前 push 开关仅保存偏好。
        </Typography.Paragraph>
      </div>
    </Drawer>
  )
}
