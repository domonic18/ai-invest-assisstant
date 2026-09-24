/** 设置页共享小组件：字段行与提示框。 */

export function DescRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs py-1">
      <span className="text-[#5c616e]">{label}</span>
      <span className="font-mono text-[#8a8f98]">{value}</span>
    </div>
  )
}

export function HintBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-md bg-[#181a21] border border-[#23262d] px-2.5 py-2 text-[11px] leading-relaxed text-[#8a8f98]">
      {children}
    </div>
  )
}
