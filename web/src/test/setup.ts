import '@testing-library/jest-dom'
import { vi } from 'vitest'

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
