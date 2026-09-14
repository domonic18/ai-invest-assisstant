/**
 * 助手子树错误边界：侧边栏组件异常降级为错误卡（可重试），
 * 不再让渲染期异常穿透成整页崩溃（React Router 错误边界兜底页）。
 */

import { Component, type ReactNode } from 'react'

interface AssistantErrorBoundaryProps {
  children: ReactNode
}

interface AssistantErrorBoundaryState {
  error: Error | null
}

export class AssistantErrorBoundary extends Component<
  AssistantErrorBoundaryProps,
  AssistantErrorBoundaryState
> {
  state: AssistantErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): AssistantErrorBoundaryState {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2.5 p-6 text-center">
        <p className="text-sm text-[#e35d6a]">助手组件出现异常</p>
        <p className="max-w-60 break-all text-xs leading-5 text-gray-500">
          {this.state.error.message}
        </p>
        <button
          type="button"
          className="rounded-md border border-white/15 px-3 py-1 text-xs text-[#c9cdd4] transition-colors hover:border-[#5e6ad2] hover:text-[#aeb4ff]"
          onClick={() => this.setState({ error: null })}
        >
          重试
        </button>
      </div>
    )
  }
}
