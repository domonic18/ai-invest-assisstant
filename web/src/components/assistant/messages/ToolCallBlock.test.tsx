/**
 * ToolCallBlock 三态渲染契约：result==null 只说明「还没等到回执」，
 * 必须叠加线程运行态才可判定执行中；线程静止仍无回执 = 已中断。
 * 钉死 2026-11-11「执行中一夜」事故的呈现层语义。
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const closePanel = vi.fn()
const setPageResult = vi.fn()
/** 可变线程运行态：模拟流存活/中断两阶段 */
let threadRunning = false

vi.mock('@/stores/assistant', () => ({
  useAssistantStore: { getState: () => ({ closePanel, setPageResult }) },
}))

vi.mock('@assistant-ui/react', () => ({
  useAuiState: (selector: (s: { thread: { isRunning: boolean } }) => unknown) =>
    selector({ thread: { isRunning: threadRunning } }),
}))

import { ToolCallBlock } from './ToolCallBlock'

/** 运行时真实形状：ToolMessage content 是 JSON 字符串携带 __event__ 标记 */
const eventResult = JSON.stringify({
  __event__: {
    type: 'kline_drawing.complete',
    target_type: 'stock',
    target_code: '600519',
    period: 'daily',
    count: 3,
  },
})

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

function renderBlock(props: { result?: unknown; toolName?: string } = {}) {
  return render(
    <MemoryRouter>
      <ToolCallBlock toolName={props.toolName ?? 'persist_chain_analysis'} args={{}} result={props.result} />
      <LocationProbe />
    </MemoryRouter>,
  )
}

describe('ToolCallBlock 三态渲染', () => {
  it('无回执且线程运行中：渲染运行中', () => {
    threadRunning = true
    renderBlock()
    expect(screen.getByText('运行中…')).toBeInTheDocument()
    expect(screen.queryByText(/已中断/)).not.toBeInTheDocument()
  })

  it('无回执且线程静止：渲染已中断而非永挂运行中', () => {
    threadRunning = false
    renderBlock()
    expect(screen.getByText('已中断 · 结果未知')).toBeInTheDocument()
    expect(screen.queryByText('运行中…')).not.toBeInTheDocument()
  })

  it('流中断（运行中→静止）后同一组件翻转为已中断', () => {
    threadRunning = true
    const { rerender } = renderBlock()
    expect(screen.getByText('运行中…')).toBeInTheDocument()

    threadRunning = false
    rerender(
      <MemoryRouter>
        <ToolCallBlock toolName="persist_chain_analysis" args={{}} result={undefined} />
      </MemoryRouter>,
    )
    expect(screen.getByText('已中断 · 结果未知')).toBeInTheDocument()
  })

  it('有回执且携带已注册页面事件：渲染已完成与查看按钮', () => {
    threadRunning = false
    renderBlock({ result: eventResult })
    expect(screen.getByText('已完成')).toBeInTheDocument()
    // antd Button 的图标 span 带 aria-label，会拼进可访问名，用正则匹配文案
    expect(screen.getByRole('button', { name: /查看 AI 画线/ })).toBeInTheDocument()
  })

  it('无回执（运行中或已中断）不渲染查看按钮', () => {
    threadRunning = true
    const { rerender } = renderBlock()
    expect(screen.queryByRole('button', { name: /查看/ })).not.toBeInTheDocument()
    threadRunning = false
    rerender(
      <MemoryRouter>
        <ToolCallBlock toolName="persist_chain_analysis" args={{}} result={undefined} />
      </MemoryRouter>,
    )
    expect(screen.queryByRole('button', { name: /查看/ })).not.toBeInTheDocument()
  })

  it('点击查看按钮：写入 pageResult、收起面板并导航到结果页', () => {
    threadRunning = false
    renderBlock({ result: eventResult })
    fireEvent.click(screen.getByRole('button', { name: /查看 AI 画线/ }))
    expect(setPageResult).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'kline_drawing.complete', targetCode: '600519' }),
    )
    expect(closePanel).toHaveBeenCalled()
    expect(screen.getByTestId('location').textContent).toBe('/stock/600519')
  })
})
