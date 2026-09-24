import { ExperimentOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  theme,
} from 'antd'
import { useEffect, useMemo, useState } from 'react'

import { useCollectorTaskCatalog } from '@/hooks/useCollectorAdmin'
import { useCollectorChannelDebug } from '@/hooks/useCollectorChannelDebug'
import type {
  CollectorChannelDebugResult,
  CollectorTaskCatalogItem,
} from '@ai-invest/shared'

import { getTaskLabel } from '@/utils/collectorTaskLabels'

const ERROR_KIND_LABEL: Record<string, string> = {
  no_collector: '该渠道未声明此数据类型的采集器',
  disabled: '渠道不可用（不存在、已禁用或凭据无法解密）',
  timeout: '采集超时',
  error: '采集异常',
}

export interface ChannelDebugTarget {
  channelId: number
  channelName: string
  supportedDataTypes: string[]
}

interface ChannelDebugModalProps {
  open: boolean
  target: ChannelDebugTarget | null
  presetDataType?: string | null
  onClose: () => void
}

export function ChannelDebugModal({
  open,
  target,
  presetDataType,
  onClose,
}: ChannelDebugModalProps) {
  const { data: catalog } = useCollectorTaskCatalog()
  const debugMutation = useCollectorChannelDebug()
  const [form] = Form.useForm()

  const catalogByName = useMemo(() => {
    const map = new Map<string, CollectorTaskCatalogItem>()
    for (const item of catalog?.items ?? []) map.set(item.name, item)
    return map
  }, [catalog])

  const dataTypeOptions = useMemo(() => {
    if (!target) return []
    const supported = target.supportedDataTypes.filter((name) =>
      catalogByName.has(name),
    )
    const rest = [...catalogByName.keys()].filter(
      (name) => !supported.includes(name),
    )
    const toOption = (name: string) => ({
      value: name,
      label: getTaskLabel(name) === name ? name : `${getTaskLabel(name)}（${name}）`,
    })
    return [...supported.map(toOption), ...rest.map(toOption)]
  }, [target, catalogByName])

  const [dataType, setDataType] = useState<string | null>(null)
  const [result, setResult] = useState<CollectorChannelDebugResult | null>(null)

  useEffect(() => {
    if (!open) return
    const initial =
      presetDataType && catalogByName.has(presetDataType)
        ? presetDataType
        : (target?.supportedDataTypes.find((name) => catalogByName.has(name)) ??
          null)
    setDataType(initial)
    setResult(null)
    debugMutation.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, target, presetDataType])

  const selectedSpec = dataType ? (catalogByName.get(dataType) ?? null) : null

  const applyDefaults = (spec: CollectorTaskCatalogItem | null) => {
    if (!spec) return
    const initial: Record<string, string> = {}
    for (const key of [...spec.configParams, ...spec.runParams]) {
      const value = spec.defaults[key]
      if (value !== undefined && value !== null) initial[key] = String(value)
    }
    form.setFieldsValue(initial)
  }

  const handleDataTypeChange = (value: string) => {
    setDataType(value)
    setResult(null)
    debugMutation.reset()
    form.resetFields()
    applyDefaults(catalogByName.get(value) ?? null)
  }

  useEffect(() => {
    if (open && selectedSpec) applyDefaults(selectedSpec)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSpec?.name, open])

  const handleRun = async (values: Record<string, string>) => {
    if (!target || !dataType) return
    const params: Record<string, string> = {}
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        params[key] = String(value).trim()
      }
    }
    const symbolsRaw = (values.__symbols ?? '') as string
    const symbols = symbolsRaw
      .split(/[,，\s]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    try {
      const res = await debugMutation.mutateAsync({
        channelId: target.channelId,
        request: {
          dataType,
          symbols: symbols.length ? symbols : null,
          params,
        },
      })
      setResult(res)
    } catch {
      // 网络层错误由全局拦截器提示，这里保持弹层打开
    }
  }

  const running = debugMutation.isPending

  return (
    <Modal
      title={
        <Space>
          <ExperimentOutlined />
          <span>调试渠道：{target?.channelName ?? '-'}</span>
        </Space>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={680}
      destroyOnClose
    >
      {!target ? null : (
        <div className="flex flex-col gap-4">
          <Form form={form} layout="vertical" onFinish={handleRun}>
            <Form.Item label="数据类型" style={{ marginBottom: 12 }}>
              <Select
                value={dataType}
                onChange={handleDataTypeChange}
                options={dataTypeOptions}
                showSearch
                optionFilterProp="label"
                placeholder="选择要试跑的数据类型"
                loading={!catalog}
              />
            </Form.Item>

            <Form.Item label="标的代码（逗号分隔，可选）" name="__symbols" style={{ marginBottom: 12 }}>
              <Input placeholder="如：000001, 600519" disabled={!selectedSpec} />
            </Form.Item>

            {selectedSpec &&
              [
                ...selectedSpec.configParams.map((key) => ({ key, kind: '配置' })),
                ...selectedSpec.runParams
                  .filter((key) => key !== 'symbols')
                  .map((key) => ({ key, kind: '参数' })),
              ].map(({ key, kind }) => (
                <Form.Item
                  key={key}
                  name={key}
                  label={`${key}（${kind}）`}
                  style={{ marginBottom: 12 }}
                >
                  <Input placeholder={String(selectedSpec.defaults[key] ?? '')} />
                </Form.Item>
              ))}

            <Button
              type="primary"
              htmlType="submit"
              icon={<ExperimentOutlined />}
              loading={running}
              disabled={!dataType}
            >
              运行调试采集
            </Button>
          </Form>

          {running && (
            <div className="flex items-center gap-2">
              <Spin size="small" />
              <Typography.Text type="secondary">
                正在采集（不落库，超时上限可在后端配置调整）…
              </Typography.Text>
            </div>
          )}

          {!running && result && <DebugResult result={result} />}
        </div>
      )}
    </Modal>
  )
}

function DebugResult({ result }: { result: CollectorChannelDebugResult }) {
  const { token } = theme.useToken()
  if (!result.ok) {
    return (
      <Alert
        type="error"
        showIcon
        message={ERROR_KIND_LABEL[result.errorKind ?? 'error'] ?? '调试失败'}
        description={result.error}
      />
    )
  }
  return (
    <div className="flex flex-col gap-2">
      <Space wrap>
        <Tag color="green">成功</Tag>
        <Typography.Text>耗时 {result.durationMs}ms</Typography.Text>
        <Typography.Text>采集 {result.collected} 条</Typography.Text>
        {result.sampleValid !== null && (
          <Typography.Text type="secondary">
            样例校验通过 {result.sampleValid}/{result.sampleItems.length}
          </Typography.Text>
        )}
      </Space>
      {result.sampleItems.length > 0 ? (
        <pre
          style={{
            margin: 0,
            padding: 12,
            overflow: 'auto',
            maxHeight: 280,
            fontSize: 12,
            lineHeight: '20px',
            borderRadius: token.borderRadiusLG,
            background: token.colorFillQuaternary,
            color: token.colorText,
          }}
        >
          {JSON.stringify(result.sampleItems, null, 2)}
        </pre>
      ) : (
        <Typography.Text type="secondary">未返回任何数据。</Typography.Text>
      )}
    </div>
  )
}
