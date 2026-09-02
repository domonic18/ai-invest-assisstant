import {
  DeleteOutlined,
  DownOutlined,
  EditOutlined,
  EllipsisOutlined,
  UpOutlined,
} from '@ant-design/icons'
import { Button, Card, Dropdown, Empty, List, Popconfirm, Switch, Tag, message } from 'antd'
import type { MenuProps } from 'antd'
import { Link } from 'react-router-dom'
import type { WatchlistGroup, WatchlistQuote } from '@ai-invest/shared'

import {
  useDeleteWatchlistGroup,
  useMoveWatchlistItem,
  useToggleGroupAiReview,
} from '@/hooks/useWatchlistGroups'
import { useRemoveWatchlistItem } from '@/hooks/useWatchlist'
import { changeColor, formatPercent } from '@/utils/formatters'

import { apiErrorMessage } from './errorMessage'

interface GroupCardProps {
  group: WatchlistGroup
  groups: WatchlistGroup[]
  quotesByCode: Map<string, WatchlistQuote>
  onEdit: (group: WatchlistGroup) => void
  onReorder: (groupIds: number[]) => void
}

export function GroupCard({ group, groups, quotesByCode, onEdit, onReorder }: GroupCardProps) {
  const toggleAi = useToggleGroupAiReview()
  const deleteGroup = useDeleteWatchlistGroup()
  const moveItem = useMoveWatchlistItem()
  const removeItem = useRemoveWatchlistItem()

  const index = groups.findIndex((g) => g.id === group.id)
  const canMoveUp = index > 0
  const canMoveDown = index >= 0 && index < groups.length - 1

  const swap = (otherIndex: number) => {
    const ids = groups.map((g) => g.id)
    ;[ids[index], ids[otherIndex]] = [ids[otherIndex], ids[index]]
    onReorder(ids)
  }

  const moveMenu = (itemId: string): MenuProps => ({
    items: groups
      .filter((g) => g.id !== group.id)
      .map((g) => ({ key: String(g.id), label: g.name })),
    onClick: ({ key }) => {
      moveItem.mutate(
        { itemId, groupId: Number(key) },
        {
          onSuccess: () => message.success('已移动'),
          onError: (err) => message.error(apiErrorMessage(err, '移动失败')),
        },
      )
    },
  })

  return (
    <Card
      title={
        <span>
          {group.name}
          {group.isDefault && <Tag className="ml-2">默认</Tag>}
        </span>
      }
      extra={
        <span className="text-xs text-gray-500">
          AI 复盘
          <Switch
            size="small"
            className="ml-2"
            checked={group.aiReviewEnabled}
            loading={toggleAi.isPending && toggleAi.variables?.groupId === group.id}
            onChange={(checked) =>
              toggleAi.mutate(
                { groupId: group.id, enabled: checked },
                { onError: (err) => message.error(apiErrorMessage(err, '开关更新失败')) },
              )
            }
          />
        </span>
      }
      actions={[
        canMoveUp ? (
          <UpOutlined key="up" onClick={() => swap(index - 1)} />
        ) : (
          <span key="up-placeholder" />
        ),
        canMoveDown ? (
          <DownOutlined key="down" onClick={() => swap(index + 1)} />
        ) : (
          <span key="down-placeholder" />
        ),
        group.isDefault ? (
          <span key="edit-placeholder" />
        ) : (
          <EditOutlined key="edit" onClick={() => onEdit(group)} />
        ),
        group.isDefault ? (
          <span key="delete-placeholder" />
        ) : (
          <Popconfirm
            key="delete"
            title="删除分组"
            description="组内股票将移入默认分组"
            okText="删除"
            cancelText="取消"
            onConfirm={() =>
              deleteGroup.mutate(group.id, {
                onSuccess: () => message.success('分组已删除'),
                onError: (err) => message.error(apiErrorMessage(err, '删除失败')),
              })
            }
          >
            <DeleteOutlined />
          </Popconfirm>
        ),
      ]}
    >
      {group.items.length ? (
        <List
          dataSource={group.items}
          renderItem={(item) => {
            const quote = quotesByCode.get(item.code)
            return (
              <List.Item
                className="!px-0"
                actions={[
                  groups.length > 1 ? (
                    <Dropdown key="move" menu={moveMenu(item.id)} placement="bottomRight">
                      <Button type="text" size="small" icon={<EllipsisOutlined />} />
                    </Dropdown>
                  ) : (
                    <span key="move-placeholder" />
                  ),
                  <Popconfirm
                    key="delete"
                    title="删除自选股"
                    description={`确定删除 ${item.code} 吗？`}
                    okText="删除"
                    cancelText="取消"
                    onConfirm={() =>
                      removeItem.mutate(item.id, {
                        onSuccess: () => message.success('已删除'),
                        onError: (err) => message.error(apiErrorMessage(err, '删除失败')),
                      })
                    }
                  >
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>,
                ]}
              >
                <div className="flex items-center justify-between w-full pr-2">
                  <div>
                    <Link to={`/stock/${item.code}`} className="font-medium">
                      {quote?.name ?? item.code}
                    </Link>
                    <span className="ml-2 text-xs text-gray-500 font-mono">{item.code}</span>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-sm">
                      {quote?.price != null ? quote.price.toFixed(2) : '-'}
                    </div>
                    <div className={`text-xs ${changeColor(quote?.changePct)}`}>
                      {quote?.changePct != null ? formatPercent(quote.changePct) : '-'}
                    </div>
                  </div>
                </div>
              </List.Item>
            )
          }}
        />
      ) : (
        <Empty description="暂无自选股" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Card>
  )
}
