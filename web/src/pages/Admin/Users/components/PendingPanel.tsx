import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { Badge, Button, Card, Empty, Space, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import type { PendingApplication } from '@ai-invest/shared'

import { usePendingApplications } from '@/hooks/useAdminAccount'

import { ApproveModal, RejectModal } from './AccountModals'

/** 待审批置顶面板：进页面即见待办、行内一键通过/驳回（arch/07 §6.3）。 */
export function PendingPanel() {
  const pendingQ = usePendingApplications()
  const [approving, setApproving] = useState<PendingApplication | null>(null)
  const [rejecting, setRejecting] = useState<PendingApplication | null>(null)

  const items = pendingQ.data ?? []
  if (!pendingQ.isLoading && items.length === 0) {
    return null
  }

  const columns: TableColumnsType<PendingApplication> = [
    {
      title: '申请时间',
      dataIndex: 'createdAt',
      width: 140,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm'),
    },
    { title: '用户名', dataIndex: 'username', width: 130 },
    { title: '邮箱', dataIndex: 'email', ellipsis: true },
    {
      title: '申请说明',
      dataIndex: 'applicationNote',
      ellipsis: true,
      render: (value: string | null) => value ?? <Tag bordered={false}>未填写</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: PendingApplication) => (
        <Space size={4}>
          <Button
            size="small"
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => setApproving(record)}
          >
            通过
          </Button>
          <Button
            size="small"
            danger
            icon={<CloseCircleOutlined />}
            onClick={() => setRejecting(record)}
          >
            驳回
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card
      variant="borderless"
      className="!border !border-[rgba(250,173,20,0.35)]"
      title={
        <Space>
          <Badge count={items.length} offset={[10, 0]} size="small">
            <span className="text-[15px]">待审批申请</span>
          </Badge>
          <span className="text-xs text-[#5c616e]">
            审批通过后用户方可登录；驳回须填原因，用户名可重新申请
          </span>
        </Space>
      }
      loading={pendingQ.isLoading}
    >
      {items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待审批申请" />
      ) : (
        <Table
          size="small"
          rowKey="id"
          dataSource={items}
          columns={columns}
          pagination={false}
          scroll={{ x: 760 }}
        />
      )}

      <ApproveModal user={approving} onClose={() => setApproving(null)} />
      <RejectModal user={rejecting} onClose={() => setRejecting(null)} />
    </Card>
  )
}
