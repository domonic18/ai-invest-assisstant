import {
  CheckCircleOutlined,
  CloudUploadOutlined,
  DownOutlined,
  FilterOutlined,
  LoadingOutlined,
  RightOutlined,
  RobotOutlined,
  SafetyOutlined,
  DatabaseOutlined,
} from '@ant-design/icons'
import { Tag } from 'antd'
import { useState, type ReactNode } from 'react'

import type { ApiAgentRunStep } from '@ai-invest/shared'

import { MarkdownContent } from '@/components/assistant/messages/MarkdownContent'
import { ReasoningBlock } from '@/components/assistant/messages/ReasoningBlock'

import { JsonView } from '../AiResults/JsonView'

/** 步骤图标：按 step_key 前缀/全名映射（未知键回落数据库图标）。 */
function stepIcon(stepKey: string): ReactNode {
  if (stepKey === 'llm') return <RobotOutlined className="text-violet-400" />
  if (stepKey === 'validate') return <FilterOutlined className="text-amber-400" />
  if (stepKey === 'persist') return <CloudUploadOutlined className="text-cyan-400" />
  if (stepKey === 'precheck') return <SafetyOutlined className="text-emerald-400" />
  if (stepKey.startsWith('input.')) return <DatabaseOutlined className="text-sky-400" />
  return <CheckCircleOutlined className="text-sky-400" />
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** llm 结构化输出中以 Markdown 呈现的自然语言段（复盘契约字段）。 */
const MARKDOWN_OUTPUT_FIELDS: { key: string; label: string }[] = [
  { key: 'overall', label: '总体复盘' },
  { key: 'market_context', label: '盘面语境' },
  { key: 'bias', label: '偏差' },
  { key: 'suggestion', label: '建议' },
]

function LlmMeta({ meta }: { meta: Record<string, unknown> }) {
  const items: string[] = []
  if (typeof meta.model_name === 'string') items.push(meta.model_name)
  if (typeof meta.latency_ms === 'number') items.push(`${(meta.latency_ms / 1000).toFixed(1)}s`)
  if (typeof meta.method === 'string') items.push(meta.method)
  if (meta.failover === true) items.push('已切备用模型')
  if (items.length === 0) return null
  return (
    <div className="mb-2 flex flex-wrap gap-1">
      {items.map((item) => (
        <Tag key={item} color="default" className="!m-0 !text-[11px]">
          {item}
        </Tag>
      ))}
    </div>
  )
}

function PromptSection({ prompt }: { prompt: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[11px] text-gray-400 transition-colors hover:text-gray-200"
      >
        {open ? '收起 Prompt 全文' : '展开 Prompt 全文'}
      </button>
      {open && (
        <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-black/30 p-2 font-mono text-[11px] text-gray-300">
          {prompt}
        </pre>
      )}
    </div>
  )
}

function LlmPayload({ payload }: { payload: Record<string, unknown> }) {
  const meta = isRecord(payload.meta) ? payload.meta : null
  const outputRecord = isRecord(payload.output) ? payload.output : null
  const markdownSections = outputRecord
    ? MARKDOWN_OUTPUT_FIELDS.filter(
        (f) => typeof outputRecord[f.key] === 'string' && outputRecord[f.key],
      )
    : []
  return (
    <div className="space-y-2">
      {typeof payload.prompt === 'string' && <PromptSection prompt={payload.prompt} />}
      {meta && <LlmMeta meta={meta} />}
      {/* 思考过程：structured 路径暂无数据源，payload.reasoning 存在才渲染（D35 预留） */}
      {typeof payload.reasoning === 'string' && <ReasoningBlock text={payload.reasoning} />}
      {markdownSections.length > 0 && (
        <div className="space-y-2 rounded bg-white/[0.03] p-3 text-xs">
          {markdownSections.map((f) => (
            <div key={f.key}>
              <div className="mb-1 text-[11px] font-medium text-gray-400">{f.label}</div>
              <MarkdownContent content={String(outputRecord![f.key])} />
            </div>
          ))}
        </div>
      )}
      {outputRecord && <JsonView data={outputRecord} />}
      {!payload.output && (
        <div className="text-[11px] text-gray-500">无输出（该步骤执行失败或被中断）</div>
      )}
    </div>
  )
}

/** 步骤 payload 渲染：llm 步用 Markdown + 元信息，其余步骤走 JSON 树。 */
export function StepPayload({ step }: { step: ApiAgentRunStep }) {
  if (!step.payload) {
    return <div className="text-[11px] text-gray-500">无 payload</div>
  }
  if (step.stepKey === 'llm') {
    return <LlmPayload payload={step.payload} />
  }
  return <JsonView data={step.payload} />
}

interface StepCardProps {
  step: ApiAgentRunStep
}

/** 聊天式时间线节点卡片：头部（图标/标题/状态/耗时）可折叠展开 payload。 */
export function StepCard({ step }: StepCardProps) {
  const failed = step.status === 'failed'
  const [open, setOpen] = useState(failed)
  return (
    <div
      className={`overflow-hidden rounded-lg border bg-white/[0.03] ${
        failed ? 'border-red-900/60' : 'border-white/10'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs"
      >
        {stepIcon(step.stepKey)}
        <span className="font-medium text-gray-200">{step.title || step.stepKey}</span>
        <span className="font-mono text-[10px] text-gray-500">{step.stepKey}</span>
        <span className="ml-auto flex items-center gap-2 text-gray-400">
          {typeof step.durationMs === 'number' && (
            <span>{step.durationMs >= 1000 ? `${(step.durationMs / 1000).toFixed(1)}s` : `${step.durationMs}ms`}</span>
          )}
          {failed ? (
            <Tag color="error" className="!m-0">
              failed
            </Tag>
          ) : (
            <Tag color="success" className="!m-0">
              success
            </Tag>
          )}
          {open ? <DownOutlined className="text-[10px]" /> : <RightOutlined className="text-[10px]" />}
        </span>
      </button>
      {open && (
        <div className="border-t border-white/10 px-3 py-2">
          <StepPayload step={step} />
        </div>
      )}
    </div>
  )
}

/** 执行中会话的未完成占位节点。 */
export function RunningStepPlaceholder() {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-sky-900/60 bg-sky-950/20 px-3 py-2 text-xs text-sky-300">
      <LoadingOutlined className="animate-spin" />
      会话执行中，步骤陆续记录…
    </div>
  )
}
