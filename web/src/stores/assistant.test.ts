import { beforeEach, describe, expect, it, vi } from 'vitest'

const STORAGE_KEY = 'ai-invest.assistant.useKb.v1'

async function loadStore() {
  const mod = await import('./assistant')
  return mod.useAssistantStore
}

describe('assistant store useKb switch', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.removeItem(STORAGE_KEY)
  })

  it('defaults to enabled', async () => {
    const store = await loadStore()
    expect(store.getState().useKb).toBe(true)
  })

  it('setUseKb persists to localStorage', async () => {
    const store = await loadStore()
    store.getState().setUseKb(false)
    expect(store.getState().useKb).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('false')

    store.getState().setUseKb(true)
    expect(store.getState().useKb).toBe(true)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('true')
  })

  it('restores persisted disabled state on reload', async () => {
    localStorage.setItem(STORAGE_KEY, 'false')
    const store = await loadStore()
    expect(store.getState().useKb).toBe(false)
  })
})
