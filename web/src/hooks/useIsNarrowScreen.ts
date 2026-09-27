import { useEffect, useState } from 'react'

/** 与 Tailwind `md:` 断点对齐（768px 以下视为窄屏/移动端）。 */
const NARROW_QUERY = '(max-width: 767px)'

function queryMatches(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(NARROW_QUERY).matches
}

export function useIsNarrowScreen(): boolean {
  const [isNarrow, setIsNarrow] = useState(queryMatches)

  useEffect(() => {
    const mql = window.matchMedia(NARROW_QUERY)
    const onChange = (event: MediaQueryListEvent) => setIsNarrow(event.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [])

  return isNarrow
}
