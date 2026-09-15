/**
 * 信息流公共骨架：跨日分组列表 + 「更新时间/自动刷新/手动刷新」工具条 + 分页。
 * 电报流与快讯流共用，条目渲染由调用方以 children 函数注入。
 */

import { ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Pagination, Space, Spin, Switch } from 'antd'
import dayjs from 'dayjs'
import type { ReactNode } from 'react'

import type { NewsDayGroup } from '../logic'

interface FeedListProps<T> {
  groups: NewsDayGroup<T>[]
  isLoading: boolean
  emptyText: string
  getKey: (item: T) => string | number
  /** 渲染单条行内容（整行 flex 容器与 key 骨架由本组件提供） */
  children: (item: T) => ReactNode
}

export function FeedList<T>({ groups, isLoading, emptyText, getKey, children }: FeedListProps<T>) {
  return (
    <Spin spinning={isLoading}>
      <Card variant="borderless">
        {groups.length === 0 && !isLoading ? (
          <Empty description={emptyText} />
        ) : (
          <div>
            {groups.map((group, groupIndex) => (
              <div key={group.day}>
                {groupIndex > 0 && (
                  <div className="flex items-center gap-2.5 my-3 text-xs opacity-40">
                    <span className="flex-1 h-px bg-white/10" />
                    以下为 {group.label} 资讯
                    <span className="flex-1 h-px bg-white/10" />
                  </div>
                )}
                {group.items.map((item) => (
                  <div key={getKey(item)}>{children(item)}</div>
                ))}
              </div>
            ))}
          </div>
        )}
      </Card>
    </Spin>
  )
}

interface FeedToolbarProps {
  dataUpdatedAt: number | undefined
  isFetching: boolean
  autoRefresh: boolean
  onAutoRefreshChange: (checked: boolean) => void
  onRefresh: () => void
  /** 工具条最左的附加位（电报流的最新电报滞后提示） */
  leading?: ReactNode
}

export function FeedToolbar({
  dataUpdatedAt,
  isFetching,
  autoRefresh,
  onAutoRefreshChange,
  onRefresh,
  leading,
}: FeedToolbarProps) {
  return (
    <Space size="middle" className="items-center">
      {leading}
      <span className="text-xs opacity-60">
        {dataUpdatedAt ? `更新于 ${dayjs(dataUpdatedAt).format('HH:mm:ss')}` : ''}
        {isFetching ? ' · 拉取中' : ''}
      </span>
      <span className="flex items-center gap-1.5 text-sm">
        <Switch size="small" checked={autoRefresh} onChange={onAutoRefreshChange} />
        自动刷新
      </span>
      <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh} />
    </Space>
  )
}

interface FeedPaginationProps {
  page: number
  pageSize: number
  total: number
  onChange: (page: number, pageSize: number) => void
}

export function FeedPagination({ page, pageSize, total, onChange }: FeedPaginationProps) {
  return (
    <div className="flex justify-end">
      <Pagination
        current={page}
        pageSize={pageSize}
        total={total}
        showSizeChanger
        pageSizeOptions={[10, 30, 50, 100]}
        showTotal={(t) => `共 ${t} 条`}
        onChange={onChange}
      />
    </div>
  )
}
