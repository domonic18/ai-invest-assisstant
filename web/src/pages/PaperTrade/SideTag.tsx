import { fallHex, riseHex } from '@/utils/formatters'

/** 买卖方向染色文本：side 1=买入（涨色）2=卖出（跌色），其余回落 '-'。 */
export function SideTag({ side }: { side: number | null | undefined }) {
  if (side === 1) return <span style={{ color: riseHex() }}>买入</span>
  if (side === 2) return <span style={{ color: fallHex() }}>卖出</span>
  return <span>-</span>
}
