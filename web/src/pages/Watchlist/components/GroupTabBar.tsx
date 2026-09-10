import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  EditOutlined,
  PictureOutlined,
  PlusOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Button, Dropdown, Modal, Space, Switch, Tabs, Tag, message } from 'antd'
import type { MenuProps } from 'antd'
import type { WatchlistGroup } from '@ai-invest/shared'

import {
  useDeleteWatchlistGroup,
  useReorderWatchlistGroups,
  useToggleGroupAiReview,
} from '@/hooks/useWatchlistGroups'
import { apiErrorMessage } from '@/utils/errorMessage'

const ALL_KEY = 'all'

interface GroupTabBarProps {
  groups: WatchlistGroup[]
  /** null 表示「全部」。 */
  activeGroupId: number | null
  onChange: (groupId: number | null) => void
  onNewGroup: () => void
  onEditGroup: (group: WatchlistGroup) => void
  onImport: () => void
}

/** 分组 Tab 栏（可横向滚动、长名截断）+ 分组管理操作区。 */
export function GroupTabBar({
  groups,
  activeGroupId,
  onChange,
  onNewGroup,
  onEditGroup,
  onImport,
}: GroupTabBarProps) {
  const deleteGroup = useDeleteWatchlistGroup()
  const reorder = useReorderWatchlistGroups()
  const toggleAi = useToggleGroupAiReview()

  const activeGroup = groups.find((g) => g.id === activeGroupId) ?? null
  const activeIndex = activeGroup ? groups.findIndex((g) => g.id === activeGroup.id) : -1

  const swap = (otherIndex: number) => {
    const ids = groups.map((g) => g.id)
    ;[ids[activeIndex], ids[otherIndex]] = [ids[otherIndex], ids[activeIndex]]
    reorder.mutate(ids, {
      onError: (err) => message.error(apiErrorMessage(err, '排序失败')),
    })
  }

  const manageMenu: MenuProps = {
    items: [
      {
        key: 'ai-review',
        disabled: !activeGroup,
        label: (
          <span
            onClick={(e) => e.stopPropagation()}
            className="flex items-center justify-between gap-3"
          >
            AI 复盘
            <Switch
              size="small"
              disabled={!activeGroup}
              checked={activeGroup?.aiReviewEnabled ?? false}
              loading={toggleAi.isPending && toggleAi.variables?.groupId === activeGroup?.id}
              onChange={(checked) => {
                if (!activeGroup) return
                toggleAi.mutate(
                  { groupId: activeGroup.id, enabled: checked },
                  { onError: (err) => message.error(apiErrorMessage(err, '开关更新失败')) },
                )
              }}
            />
          </span>
        ),
      },
      { type: 'divider' },
      {
        key: 'move-up',
        icon: <ArrowUpOutlined />,
        label: '上移分组',
        disabled: !activeGroup || activeIndex <= 0,
        onClick: () => swap(activeIndex - 1),
      },
      {
        key: 'move-down',
        icon: <ArrowDownOutlined />,
        label: '下移分组',
        disabled: !activeGroup || activeIndex >= groups.length - 1,
        onClick: () => swap(activeIndex + 1),
      },
      { type: 'divider' },
      {
        key: 'edit',
        icon: <EditOutlined />,
        label: '编辑分组',
        disabled: !activeGroup || activeGroup.isDefault,
        onClick: () => activeGroup && onEditGroup(activeGroup),
      },
      {
        key: 'delete',
        icon: <DeleteOutlined />,
        danger: true,
        disabled: !activeGroup || activeGroup.isDefault,
        label: '删除分组',
        onClick: () => {
          if (!activeGroup) return
          Modal.confirm({
            title: '删除分组',
            content: '组内股票将移入默认分组',
            okText: '删除',
            okButtonProps: { danger: true },
            cancelText: '取消',
            onOk: () =>
              deleteGroup.mutateAsync(activeGroup.id).then(() => {
                message.success('分组已删除')
                onChange(null)
              }),
          })
        },
      },
    ],
  }

  return (
    <div className="shrink-0 border-b border-gray-800 px-3">
      <Tabs
        size="small"
        activeKey={activeGroupId === null ? ALL_KEY : String(activeGroupId)}
        onChange={(key) => onChange(key === ALL_KEY ? null : Number(key))}
        className="[&_.ant-tabs-nav]:!mb-0"
        items={[
          {
            key: ALL_KEY,
            label: (
              <span>
                全部
                <span className="ml-1 text-xs text-gray-500">
                  {groups.reduce((sum, g) => sum + g.items.length, 0)}
                </span>
              </span>
            ),
          },
          ...groups.map((g) => ({
            key: String(g.id),
            label: (
              <span className="inline-flex items-center max-w-[120px]">
                <span className="truncate">{g.name}</span>
                {g.isDefault && <Tag className="ml-1 !mr-0 !text-[10px]">默认</Tag>}
                <span className="ml-1 text-xs text-gray-500">{g.items.length}</span>
              </span>
            ),
          })),
        ]}
        tabBarExtraContent={
          <Space size={4}>
            <Button size="small" icon={<PictureOutlined />} onClick={onImport}>
              截图导入
            </Button>
            <Button size="small" type="primary" icon={<PlusOutlined />} onClick={onNewGroup}>
              新建分组
            </Button>
            <Dropdown menu={manageMenu} placement="bottomRight" trigger={['click']}>
              <Button size="small" icon={<SettingOutlined />}>
                分组管理
              </Button>
            </Dropdown>
          </Space>
        }
      />
    </div>
  )
}
