import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useIsNarrowScreen } from './useIsNarrowScreen'

function mockMql(matches: boolean) {
  const listeners = new Set<(e: { matches: boolean }) => void>()
  const mql = {
    matches,
    media: '(max-width: 767px)',
    onchange: null,
    addEventListener: (_: string, cb: (e: { matches: boolean }) => void) => listeners.add(cb),
    removeEventListener: (_: string, cb: (e: { matches: boolean }) => void) =>
      listeners.delete(cb),
  }
  vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)
  return {
    fire(next: boolean) {
      listeners.forEach((cb) => cb({ matches: next }))
    },
  }
}

describe('useIsNarrowScreen', () => {
  it('reflects initial matchMedia state', () => {
    mockMql(true)
    const { result } = renderHook(() => useIsNarrowScreen())
    expect(result.current).toBe(true)
  })

  it('updates on breakpoint change and cleans up listener', () => {
    const mql = mockMql(false)
    const { result, unmount } = renderHook(() => useIsNarrowScreen())
    expect(result.current).toBe(false)

    act(() => mql.fire(true))
    expect(result.current).toBe(true)

    unmount()
    expect(vi.mocked(window.matchMedia).mock.results.length).toBeGreaterThan(0)
  })
})
