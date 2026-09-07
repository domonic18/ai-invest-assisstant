import { useEffect, useRef, useState } from 'react'

import { CHROME_HEIGHT } from './StockChartView'

/** 根元素 requestFullscreen，画布高度跟随窗口；CHROME_HEIGHT 为工具栏+底边框。 */
export function useChartFullscreen() {
  const rootRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [fsHeight, setFsHeight] = useState<number | null>(null)

  useEffect(() => {
    const onFsChange = () => {
      const active = document.fullscreenElement === rootRef.current
      setIsFullscreen(active)
      setFsHeight(active ? window.innerHeight - CHROME_HEIGHT - 2 : null)
    }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  const toggleFullscreen = () => {
    if (document.fullscreenElement != null) {
      void document.exitFullscreen()
    } else {
      void rootRef.current?.requestFullscreen()
    }
  }

  return { rootRef, isFullscreen, fsHeight, toggleFullscreen }
}
