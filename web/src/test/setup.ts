import '@testing-library/jest-dom'
import { act } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// jsdom 未实现 getComputedStyle(elt, pseudoElt) 双参调用（Not implemented，
// 以 unhandled error 使 vitest 退出码非零）；antd Modal 的 scrollLocker
// 经 rc-util 量滚动条宽度会触发，polyfill 返回 0 尺寸伪样式
const origGetComputedStyle = window.getComputedStyle.bind(window)
window.getComputedStyle = ((elt: Element, pseudoElt?: string | null) => {
  if (pseudoElt) {
    return { width: '0px', height: '0px' } as CSSStyleDeclaration
  }
  return origGetComputedStyle(elt)
}) as typeof window.getComputedStyle

// React 的 scheduler 队列可能还压着未 flush 的更新（antd 动画回调、async 续体）。
// 用例跑完、jsdom 环境销毁之后这些任务才执行，react-dom 的 prepareForCommit 会
// 直接读全局 window（此时已不存在）→ unhandled error → vitest 退出码非零
// （CI 曾以 "window is not defined" 偶发红，测试断言本身全过）。
// 环境销毁前先把队列跑空。本 hook 在 setup.ts 注册，早于 RTL 的自动 cleanup；
// vitest 的 after 钩子按 stack 序（后注册先执行），故 cleanup 先跑、本 hook 最后跑——
// 卸载已完成，这里只负责把残留任务在环境销毁前消化掉。
afterEach(async () => {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
})
