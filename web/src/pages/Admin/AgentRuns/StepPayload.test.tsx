import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ApiAgentRunStep } from '@ai-invest/shared'

import { RunningStepPlaceholder, StepCard, StepPayload } from './StepPayload'

function makeStep(overrides: Partial<ApiAgentRunStep> = {}): ApiAgentRunStep {
  return {
    seq: 1,
    stepKey: 'input.kb_methodology',
    title: 'KB 方法论检索',
    status: 'success',
    startedAt: '2026-09-26T11:30:05+00:00',
    durationMs: 320,
    payload: { source_id: 3, relevant_counts: { disciplines: 4 } },
    ...overrides,
  }
}

describe('StepPayload', () => {
  it('renders non-llm step as JSON tree', () => {
    render(<StepPayload step={makeStep()} />)
    // 基本值键渲染为 "source_id: "（冒号尾随），子对象键无冒号
    expect(screen.getByText('source_id', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('relevant_counts')).toBeInTheDocument()
  })

  it('renders llm step with markdown sections and meta tags', () => {
    render(
      <StepPayload
        step={makeStep({
          stepKey: 'llm',
          title: 'LLM 结构化生成',
          durationMs: 9200,
          payload: {
            prompt: '你是短线猎手的计划官',
            meta: { model_name: 'kimi', latency_ms: 9200, method: 'json_schema' },
            output: {
              overall: '整体执行纪律良好',
              market_context: '主线板块发酵期',
              bias: '偏乐观',
              suggestion: '严格执行买点纪律',
            },
          },
        })}
      />,
    )
    // 复盘契约 Markdown 段（非 JSON 树重复渲染）
    expect(screen.getByText('总体复盘')).toBeInTheDocument()
    expect(screen.getByText('盘面语境')).toBeInTheDocument()
    expect(screen.getByText('偏差')).toBeInTheDocument()
    expect(screen.getByText('建议')).toBeInTheDocument()
    // 元信息 tags：模型名 / 耗时 / 解析法
    expect(screen.getByText('kimi')).toBeInTheDocument()
    expect(screen.getByText('9.2s')).toBeInTheDocument()
    expect(screen.getByText('json_schema')).toBeInTheDocument()
    // Prompt 全文默认折叠
    expect(screen.getByText('展开 Prompt 全文')).toBeInTheDocument()
    expect(screen.queryByText('你是短线猎手的计划官')).not.toBeInTheDocument()
  })

  it('renders llm step without output as empty placeholder', () => {
    render(
      <StepPayload
        step={makeStep({
          stepKey: 'llm',
          payload: { prompt: 'p', meta: {} },
        })}
      />,
    )
    expect(screen.getByText('无输出（该步骤执行失败或被中断）')).toBeInTheDocument()
  })

  it('renders payload-less step placeholder', () => {
    render(<StepPayload step={makeStep({ payload: null })} />)
    expect(screen.getByText('无 payload')).toBeInTheDocument()
  })
})

describe('StepCard', () => {
  it('keeps success step collapsed until header click', () => {
    render(<StepCard step={makeStep()} />)
    expect(screen.queryByText('source_id', { exact: false })).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('KB 方法论检索'))
    expect(screen.getByText('source_id', { exact: false })).toBeInTheDocument()
  })

  it('auto-expands failed step', () => {
    render(
      <StepCard
        step={makeStep({
          status: 'failed',
          stepKey: 'validate',
          title: '后置校验',
          payload: { dropped_codes: ['999999'] },
        })}
      />,
    )
    expect(screen.getByText('dropped_codes')).toBeInTheDocument()
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0)
  })

  it('renders duration in human form', () => {
    render(<StepCard step={makeStep({ durationMs: 9200 })} />)
    expect(screen.getByText('9.2s')).toBeInTheDocument()
  })
})

describe('RunningStepPlaceholder', () => {
  it('renders running hint', () => {
    render(<RunningStepPlaceholder />)
    expect(screen.getByText('会话执行中，步骤陆续记录…')).toBeInTheDocument()
  })
})
