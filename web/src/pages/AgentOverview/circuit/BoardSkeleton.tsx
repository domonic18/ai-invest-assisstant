/**
 * 主板加载骨架：模拟电路主板版图（主控/芯片插槽/外设/逻辑分析仪）的
 * 灰块占位（animate-pulse），首屏 isLoading 时替代整板渲染，消除数据到达前的闪跳。
 */
const BOARD_ASPECT = '1140 / 800'

/** 版图坐标（与原型 1140×800 同系）→ 百分比定位的灰块。 */
const BLOCKS: ReadonlyArray<{ x: number; y: number; w: number; h: number; r?: number }> = [
  { x: 430, y: 334, w: 210, h: 150, r: 12 },
  { x: 820, y: 186, w: 120, h: 84, r: 10 },
  { x: 850, y: 496, w: 120, h: 84, r: 10 },
  { x: 850, y: 640, w: 120, h: 84, r: 10 },
  { x: 74, y: 130, w: 110, h: 57, r: 8 },
  { x: 60, y: 248, w: 110, h: 40, r: 8 },
  { x: 60, y: 316, w: 110, h: 40, r: 8 },
  { x: 60, y: 420, w: 310, h: 315, r: 12 },
  { x: 1010, y: 330, w: 100, h: 92, r: 10 },
  { x: 380, y: 640, w: 280, h: 60, r: 10 },
]

export function BoardSkeleton() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="主板加载中"
      className="relative min-h-0 flex-1 overflow-hidden rounded-[18px] border border-[#23262d] bg-[#0a0f0d] shadow-[0_24px_70px_rgba(0,0,0,.6)]"
      style={{ aspectRatio: BOARD_ASPECT }}
    >
      <div className="absolute inset-0">
        {BLOCKS.map((b, i) => (
          <div
            key={i}
            className="animate-pulse border border-white/[0.04] bg-white/[0.05]"
            style={{
              position: 'absolute',
              left: `${(b.x / 1140) * 100}%`,
              top: `${(b.y / 800) * 100}%`,
              width: `${(b.w / 1140) * 100}%`,
              height: `${(b.h / 800) * 100}%`,
              borderRadius: b.r ?? 8,
              animationDelay: `${i * 120}ms`,
            }}
          />
        ))}
        <div className="absolute bottom-[3.5%] left-[5%] h-[6px] w-[18%] animate-pulse rounded bg-white/[0.04]" />
      </div>
    </div>
  )
}
