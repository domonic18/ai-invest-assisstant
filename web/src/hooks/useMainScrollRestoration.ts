import { useEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

const STORAGE_KEY = 'ai-invest.layout.main-scroll'
const MAX_ENTRIES = 30

type PositionMap = Record<string, number>

function readMap(): PositionMap {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as PositionMap) : {}
  } catch {
    return {}
  }
}

function writeMap(map: PositionMap): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map))
  } catch {
    // ignore quota/serialization errors
  }
}

/**
 * Layout 主滚动容器（<main>，window 不滚动）的路由级滚动位置记忆：
 * 滚动时按 pathname 记录 scrollTop（rAF 节流 + sessionStorage），浏览器返回
 * （POP）时恢复原位——解决复盘页→个股详情→返回后回到页首的问题；PUSH/
 * REPLACE 进入新页面复位顶部。恢复用双 rAF 等内容首帧提交后再定位，且恢复
 * 引起的钳制滚动不回写（内容未长回原高度时保留原记录）。
 */
export function useMainScrollRestoration() {
  const ref = useRef<HTMLElement | null>(null)
  const skipSaveRef = useRef(false)
  const location = useLocation()
  const navType = useNavigationType()
  const routeKey = location.pathname + location.search

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (navType === 'POP') {
      const saved = readMap()[routeKey]
      if (saved == null) return
      skipSaveRef.current = true
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.scrollTop = saved
          requestAnimationFrame(() => {
            skipSaveRef.current = false
          })
        })
      })
    } else {
      el.scrollTop = 0
    }
  }, [routeKey, navType])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let raf = 0
    const onScroll = () => {
      if (raf || skipSaveRef.current) return
      raf = requestAnimationFrame(() => {
        raf = 0
        const map = readMap()
        map[routeKey] = el.scrollTop
        const keys = Object.keys(map)
        if (keys.length > MAX_ENTRIES) delete map[keys[0]]
        writeMap(map)
      })
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      el.removeEventListener('scroll', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [routeKey])

  return ref
}
