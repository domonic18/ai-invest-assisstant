import {
  AudioOutlined,
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  KeyOutlined,
  PlaySquareOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Col,
  Popconfirm,
  Row,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ApiSocialAccountAdmin } from '@ai-invest/shared'
import { useState } from 'react'

import {
  useAsrConfig,
  useBackfillSocialAccount,
  useCreateSocialAccount,
  useDeleteSocialAccount,
  useImportSocialCookie,
  useSocialAccountsAdmin,
  useSocialAdminStatus,
  useUpdateAsrConfig,
  useUpdateSocialAccount,
} from '@/hooks/useAdminSocial'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'

import { AsrConfigModal } from './AsrConfigModal'
import { CookieImportModal } from './CookieImportModal'
import { PostsDebugDrawer } from './PostsDebugDrawer'
import { SocialAccountModal } from './SocialAccountModal'

const PAGE_SIZE = 20

const CATEGORY_LABEL: Record<string, string> = {
  finance_kol: '财经KOL',
  macro_policy: '宏观政策',
  industry: '行业',
}

function StatusCard({
  title,
  items,
  warning,
}: {
  title: string
  items: { label: string; value: React.ReactNode }[]
  warning?: string | null
}) {
  return (
    <Card variant="borderless" title={title} size="small">
      {warning && (
        <Alert className="mb-3" type="warning" showIcon message={warning} />
      )}
      <Row gutter={[12, 8]}>
        {items.map((item) => (
          <Col span={8} key={item.label}>
            <div className="text-xs text-white/45">{item.label}</div>
            <div className="text-base">{item.value}</div>
          </Col>
        ))}
      </Row>
    </Card>
  )
}

export function SocialTracking() {
  const [page, setPage] = useState(1)
  const accountsQuery = useSocialAccountsAdmin(page, PAGE_SIZE)
  const statusQuery = useSocialAdminStatus()
  const asrConfigQuery = useAsrConfig()
  const createMutation = useCreateSocialAccount(page, PAGE_SIZE)
  const updateMutation = useUpdateSocialAccount(page, PAGE_SIZE)
  const deleteMutation = useDeleteSocialAccount(page, PAGE_SIZE)
  const backfillMutation = useBackfillSocialAccount(page, PAGE_SIZE)
  const importCookieMutation = useImportSocialCookie()
  const updateAsrMutation = useUpdateAsrConfig()

  const [accountModalOpen, setAccountModalOpen] = useState(false)
  const [editingAccount, setEditingAccount] = useState<ApiSocialAccountAdmin | null>(null)
  const [cookieModalOpen, setCookieModalOpen] = useState(false)
  const [asrModalOpen, setAsrModalOpen] = useState(false)
  const [postsAccount, setPostsAccount] = useState<ApiSocialAccountAdmin | null>(null)

  const douyin = statusQuery.data?.douyin
  const asr = statusQuery.data?.asr

  const handleError = (err: unknown, fallback: string) =>
    message.error(err instanceof Error ? err.message : fallback)

  const handleToggle = async (record: ApiSocialAccountAdmin, isActive: boolean) => {
    try {
      await updateMutation.mutateAsync({ id: record.id, data: { isActive } })
      message.success(isActive ? `已启用「${record.alias}」` : `已停用「${record.alias}」`)
    } catch (err) {
      handleError(err, '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('账号已删除（判断历史随删）')
    } catch (err) {
      handleError(err, '删除失败')
    }
  }

  const handleBackfill = async (record: ApiSocialAccountAdmin) => {
    try {
      await backfillMutation.mutateAsync(record.id)
      message.success(`「${record.alias}」回填采集已派发，进度见采集日志`)
    } catch (err) {
      handleError(err, '回填派发失败')
    }
  }

  const handleSubmitAccount = async (values: {
    secUidOrUrl?: string
    alias: string
    category: string
    pollIntervalMinutes: number
    remark?: string | null
  }) => {
    try {
      if (editingAccount) {
        await updateMutation.mutateAsync({
          id: editingAccount.id,
          data: {
            alias: values.alias,
            category: values.category,
            pollIntervalMinutes: values.pollIntervalMinutes,
            remark: values.remark ?? null,
          },
        })
        message.success('账号已更新')
      } else {
        await createMutation.mutateAsync({
          secUidOrUrl: values.secUidOrUrl ?? '',
          alias: values.alias,
          category: values.category,
          pollIntervalMinutes: values.pollIntervalMinutes,
          remark: values.remark ?? null,
        })
        message.success('账号已登记，等待下一轮采集')
      }
      setAccountModalOpen(false)
    } catch (err) {
      handleError(err, '保存失败')
    }
  }

  const handleImportCookie = async (cookie: string) => {
    try {
      const result = await importCookieMutation.mutateAsync({ cookie })
      message.success(`导入成功，当前可用 ${result.cookieJarsAvailable} 个 Cookie`)
      setCookieModalOpen(false)
    } catch (err) {
      handleError(err, '导入失败')
    }
  }

  const handleSaveAsr = async (values: {
    baseUrl?: string
    model?: string
    apiKey?: string
    maxAudioSeconds?: number
    hotwords?: string[]
    enabled?: boolean
  }) => {
    try {
      await updateAsrMutation.mutateAsync(values)
      message.success('ASR 配置已保存，即刻生效')
      setAsrModalOpen(false)
    } catch (err) {
      handleError(err, '保存失败')
    }
  }

  const columns = [
    { title: '账号', dataIndex: 'alias', key: 'alias' },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (v: string) => <Tag>{CATEGORY_LABEL[v] ?? v}</Tag>,
    },
    {
      title: '轮询',
      dataIndex: 'pollIntervalMinutes',
      key: 'pollIntervalMinutes',
      width: 80,
      render: (v: number) => `${v}m`,
    },
    {
      title: '启用',
      dataIndex: 'isActive',
      key: 'isActive',
      width: 80,
      render: (value: boolean, record: ApiSocialAccountAdmin) => (
        <Switch
          checked={value}
          loading={updateMutation.isPending && updateMutation.variables?.id === record.id}
          onChange={(checked) => handleToggle(record, checked)}
        />
      ),
    },
    {
      title: '最新作品',
      dataIndex: 'lastPostAt',
      key: 'lastPostAt',
      width: 140,
      render: (v: string | null) => (v ? formatRelativeTime(v) : '-'),
    },
    {
      title: '最近采集',
      dataIndex: 'lastCollectedAt',
      key: 'lastCollectedAt',
      width: 140,
      render: (v: string | null) => (v ? formatRelativeTime(v) : '-'),
    },
    {
      title: '最近错误',
      dataIndex: 'lastError',
      key: 'lastError',
      ellipsis: true,
      render: (v: string | null, record: ApiSocialAccountAdmin) =>
        v ? (
          <Tooltip title={`${formatDateTime(record.lastErrorAt)}\n${v}`}>
            <Typography.Text type="danger" ellipsis={{ tooltip: false }}>
              {v}
            </Typography.Text>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 300,
      render: (_: unknown, record: ApiSocialAccountAdmin) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingAccount(record)
              setAccountModalOpen(true)
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            icon={<PlaySquareOutlined />}
            onClick={() => setPostsAccount(record)}
          >
            作品
          </Button>
          <Popconfirm
            title="回填采集该账号历史视频？"
            description="忽略增量水位深拉约 200 条，逐条 ASR 转写（费时费钱）；作品即时入库可见，中断后可重新触发续传，已完成部分自动跳过"
            onConfirm={() => handleBackfill(record)}
          >
            <Button
              size="small"
              icon={<HistoryOutlined />}
              loading={backfillMutation.isPending && backfillMutation.variables === record.id}
            >
              回填
            </Button>
          </Popconfirm>
          <Popconfirm
            title="确认删除该账号？"
            description="该账号的判断历史将一并删除"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <StatusCard
            title="抖音采集"
            items={[
              {
                label: 'Cookie 池',
                value: douyin?.cookieConfigured ? `${douyin.cookieJarsAvailable} 个可用` : '未配置',
              },
              { label: '今日采集', value: douyin?.todayCollected ?? '-' },
              { label: '今日失败', value: douyin?.todayFailed ?? '-' },
              {
                label: '最近自举',
                value: douyin?.lastBootstrapAt ? formatDateTime(douyin.lastBootstrapAt) : '-',
              },
            ]}
            warning={douyin?.signatureWarning ? '检测到签名错误（a_bogus 可能被跟版），请关注采集任务状态' : null}
          />
        </Col>
        <Col xs={24} lg={12}>
          <StatusCard
            title="ASR 转写"
            items={[
              {
                label: '服务状态',
                value: asr ? (asr.enabled ? (asr.configured ? '正常' : '未配置密钥') : '已关闭') : '-',
              },
              { label: '今日转写', value: asr?.todayTranscribed ?? '-' },
              { label: '今日排队', value: asr?.todayPending ?? '-' },
              { label: '今日降级', value: asr?.todayDegraded ?? '-' },
            ]}
            warning={
              asr && (!asr.enabled || !asr.configured)
                ? '转写未生效：新内容判断仅基于标题/文案'
                : null
            }
          />
        </Col>
      </Row>

      <Card
        title="追踪账号"
        variant="borderless"
        extra={
          <Space>
            <Button
              icon={<KeyOutlined />}
              onClick={() => setCookieModalOpen(true)}
            >
              导入 Cookie
            </Button>
            <Button icon={<AudioOutlined />} onClick={() => setAsrModalOpen(true)}>
              ASR 配置
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingAccount(null)
                setAccountModalOpen(true)
              }}
            >
              登记账号
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={accountsQuery.data?.items ?? []}
          columns={columns}
          rowKey="id"
          loading={accountsQuery.isLoading}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: accountsQuery.data?.total ?? 0,
            showSizeChanger: false,
            onChange: setPage,
          }}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <SocialAccountModal
        open={accountModalOpen}
        editing={editingAccount}
        loading={createMutation.isPending || updateMutation.isPending}
        onCancel={() => setAccountModalOpen(false)}
        onSubmit={handleSubmitAccount}
      />
      <CookieImportModal
        open={cookieModalOpen}
        loading={importCookieMutation.isPending}
        onCancel={() => setCookieModalOpen(false)}
        onSubmit={handleImportCookie}
      />
      <AsrConfigModal
        open={asrModalOpen}
        config={asrConfigQuery.data ?? null}
        loading={updateAsrMutation.isPending}
        onCancel={() => setAsrModalOpen(false)}
        onSubmit={handleSaveAsr}
      />
      <PostsDebugDrawer account={postsAccount} onClose={() => setPostsAccount(null)} />
    </div>
  )
}
