import {
  CaretRightOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { useEffect, useMemo } from 'react'

import { useCollectorTaskChannels } from '@/hooks/useCollectorAdmin'
import type {
  CollectorTaskName,
  CollectorTaskOption,
  CollectorTaskRunOptions,
} from '@ai-invest/shared'

const AUTO_RESOLVE_LABEL = '系统自动选择'

interface CollectorTaskModalProps {
  open: boolean
  task: CollectorTaskOption | null
  onCancel: () => void
  onSubmit: (taskName: CollectorTaskName, options: CollectorTaskRunOptions) => void
  loading: boolean
}

interface TaskFormValues {
  preferredSource?: string
  symbols?: string
  period?: string
  startDate?: string
  endDate?: string
  sectorType?: string
  indicators?: string[]
  reportTypes?: string[]
  reportDate?: string
}

const PERIOD_OPTIONS = [
  { value: 'daily', label: '日线' },
  { value: 'minute', label: '分钟线' },
]

const SECTOR_TYPE_OPTIONS = [
  { value: 'industry', label: '行业' },
  { value: 'concept', label: '概念' },
  { value: 'region', label: '地域' },
]

const MACRO_INDICATOR_OPTIONS = [
  { value: 'cpi', label: 'CPI' },
  { value: 'pmi', label: 'PMI' },
  { value: 'gdp', label: 'GDP' },
]

const FINANCIAL_REPORT_TYPE_OPTIONS = [
  { value: '年报', label: '年报' },
  { value: '半年报', label: '半年报' },
  { value: '一季报', label: '一季报' },
  { value: '三季报', label: '三季报' },
]

function parseSymbols(input: string | undefined): string[] | undefined {
  if (!input) return undefined
  const symbols = input
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  return symbols.length > 0 ? symbols : undefined
}

export function CollectorTaskModal({
  open,
  task,
  onCancel,
  onSubmit,
  loading,
}: CollectorTaskModalProps) {
  const [form] = Form.useForm<TaskFormValues>()
  const preferredSource = Form.useWatch('preferredSource', form)
  const { data, isLoading, error } = useCollectorTaskChannels(task?.key ?? null)

  const channelOptions = useMemo(
    () =>
      data?.channels.map((channel) => ({
        value: channel.source,
        label: `${channel.name} (${channel.source})`,
      })) ?? [],
    [data],
  )

  const selectedChannelName = useMemo(() => {
    if (!data) return undefined
    const source = preferredSource ?? data.resolved_source
    return data.channels.find((c) => c.source === source)?.name ?? source
  }, [data, preferredSource])

  useEffect(() => {
    if (open && data) {
      form.setFieldsValue({
        preferredSource: data.resolved_source ?? undefined,
        symbols: undefined,
        period: 'daily',
        startDate: undefined,
        endDate: undefined,
        sectorType: 'industry',
        indicators: ['cpi', 'pmi', 'gdp'],
        reportTypes: ['年报', '半年报', '一季报', '三季报'],
        reportDate: undefined,
      })
    }
  }, [open, data, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    if (task) {
      onSubmit(task.key, {
        preferredSource: values.preferredSource,
        symbols: parseSymbols(values.symbols),
        period: values.period,
        startDate: values.startDate,
        endDate: values.endDate,
        sectorType: values.sectorType,
        indicators: values.indicators,
        reportTypes: values.reportTypes,
        reportDate: values.reportDate,
      })
    }
  }

  return (
    <Modal
      title={task ? `触发：${task.label}` : '触发采集任务'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="run"
          type="primary"
          icon={<CaretRightOutlined />}
          loading={loading}
          onClick={handleOk}
        >
          开始采集
        </Button>,
      ]}
    >
      {error ? (
        <Alert
          message="加载可用渠道失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      ) : isLoading || !data ? (
        <Space className="py-8" size="middle">
          <Spin />
          <Typography.Text type="secondary">正在解析可用渠道...</Typography.Text>
        </Space>
      ) : (
        <Form form={form} layout="vertical" autoComplete="off">
          <Alert
            message={
              <Space>
                <ExclamationCircleOutlined />
                <span>
                  {preferredSource ? '已指定渠道：' : '将使用渠道：'}
                  <Tag color={preferredSource ? 'green' : 'blue'}>
                    {selectedChannelName || '无可用渠道'}
                  </Tag>
                  {!preferredSource && data.resolved_source && (
                    <Typography.Text type="secondary" className="ml-2">
                      （{AUTO_RESOLVE_LABEL}）
                    </Typography.Text>
                  )}
                </span>
              </Space>
            }
            type="info"
            showIcon={false}
            className="mb-4"
          />

          <Form.Item label="指定渠道（可选）" name="preferredSource">
            <Select
              allowClear
              placeholder="留空则系统自动选择"
              options={channelOptions}
              disabled={channelOptions.length === 0}
            />
          </Form.Item>

          <Collapse
            ghost
            items={[
              {
                key: 'advanced',
                label: '高级选项',
                children: (
                  <>
                    {task?.key === 'kline' && (
                      <Form.Item label="周期" name="period">
                        <Select options={PERIOD_OPTIONS} />
                      </Form.Item>
                    )}
                    {(task?.key === 'disclosure' || task?.key === 'dragon-list') && (
                      <>
                        <Form.Item label="开始日期" name="startDate">
                          <Input placeholder="YYYY-MM-DD" />
                        </Form.Item>
                        <Form.Item label="结束日期" name="endDate">
                          <Input placeholder="YYYY-MM-DD" />
                        </Form.Item>
                      </>
                    )}
                    {task?.key === 'financial-report' && (
                      <>
                        <Form.Item label="财报类型" name="reportTypes">
                          <Checkbox.Group options={FINANCIAL_REPORT_TYPE_OPTIONS} />
                        </Form.Item>
                        <Form.Item label="开始日期" name="startDate">
                          <Input placeholder="YYYY-MM-DD" />
                        </Form.Item>
                        <Form.Item label="结束日期" name="endDate">
                          <Input placeholder="YYYY-MM-DD" />
                        </Form.Item>
                      </>
                    )}
                    {task?.key === 'fund-holdings' && (
                      <Form.Item
                        label="财报日期"
                        name="reportDate"
                        help="如 20250331，留空使用默认值"
                      >
                        <Input placeholder="YYYYMMDD" />
                      </Form.Item>
                    )}
                    {task?.key === 'sector-fund-flow' && (
                      <Form.Item label="板块类型" name="sectorType">
                        <Select options={SECTOR_TYPE_OPTIONS} />
                      </Form.Item>
                    )}
                    {task?.key === 'macro' && (
                      <Form.Item label="指标" name="indicators">
                        <Checkbox.Group options={MACRO_INDICATOR_OPTIONS} />
                      </Form.Item>
                    )}
                    <Form.Item
                      label="股票代码"
                      name="symbols"
                      help="逗号分隔，留空则使用默认股票列表"
                    >
                      <Input.TextArea
                        rows={2}
                        placeholder="000001,000002,600000"
                      />
                    </Form.Item>
                  </>
                ),
              },
            ]}
          />
        </Form>
      )}
    </Modal>
  )
}
