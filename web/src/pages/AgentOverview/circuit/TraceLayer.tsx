/**
 * 主板走线层：热通路辉光 + 信号走线（丝印标注语义）+ 过孔 + 电子脉冲。
 * 芯片相关走线按插槽 Y 参数化：启用芯片 = 身份色双流（计划/盯盘）+ 时钟树；
 * 有当日委托 = 红色 ORDER 热通路；未启用 = 灰色断线（NO POWER）。
 */
import { BOARD } from './boardTheme'

export interface ChipTraceTarget {
  y: number
  enabled: boolean
  accent: string
  hasOrders: boolean
}

export function TraceLayer({
  chips,
  reducedMotion,
}: {
  chips: ChipTraceTarget[]
  reducedMotion: boolean
}) {
  const liveChips = chips.filter((c) => c.enabled)
  const firstLive = liveChips[0]
  const firstOrder = liveChips.find((c) => c.hasOrders)

  return (
    <g>
      {/* 热通路辉光底层 */}
      {firstLive && (
        <path
          d={`M640 356 H760 V${firstLive.y + 54} H820`}
          fill="none"
          stroke={BOARD.cyan}
          strokeOpacity=".22"
          strokeWidth="8"
          filter="url(#ahc-softC)"
        />
      )}
      {firstOrder && (
        <path
          d={`M940 ${firstOrder.y + 54} H1000 V376 H1010`}
          fill="none"
          stroke={BOARD.red}
          strokeOpacity=".2"
          strokeWidth="7"
          filter="url(#ahc-softC)"
        />
      )}

      {/* 资源站 → 主控（固定拓扑） */}
      <path d="M170 170 H300 V356 H430" fill="none" stroke="rgba(168,85,247,.5)" strokeWidth="2.4" className="ahc-trace-fast" />
      <path d="M170 274 H340 V400 H430" fill="none" stroke="rgba(88,166,255,.45)" strokeWidth="2" className="ahc-trace-slow" />
      <path d="M170 337 H360 V430 H430" fill="none" stroke="rgba(244,114,182,.4)" strokeWidth="2" className="ahc-trace-slow" />

      {/* 主控 → 芯片：计划/盯盘双流（身份色） */}
      {liveChips.map((chip, i) => (
        <g key={`live-${chip.y}`}>
          <path
            d={`M640 356 H${700 + i * 30} V${chip.y + 54} H820`}
            fill="none"
            stroke={chip.accent}
            strokeOpacity=".9"
            strokeWidth="3.2"
            className="ahc-trace-fast"
          />
          <path
            d={`M640 372 H${680 + i * 30} V${chip.y + 82} H820`}
            fill="none"
            stroke={chip.accent}
            strokeOpacity=".5"
            strokeWidth="1.8"
            className="ahc-trace-fast"
          />
          <path
            d={`M626 ${541 + i * 12} H${660 + i * 20} V${chip.y + 42} H820`}
            fill="none"
            stroke="rgba(148,163,184,.3)"
            strokeWidth="1.2"
            className="ahc-trace-clk"
          />
        </g>
      ))}

      {/* 芯片 → 模拟柜台：ORDER 热通路（红，仅当日有委托） */}
      {liveChips
        .filter((chip) => chip.hasOrders)
        .map((chip) => (
          <path
            key={`order-${chip.y}`}
            d={`M940 ${chip.y + 54} H1000 V376 H1010`}
            fill="none"
            stroke="rgba(248,81,73,.7)"
            strokeWidth="2.6"
            className="ahc-trace-fast"
          />
        ))}

      {/* 主控 → Celery 总线 */}
      <path d="M535 484 V560 H520 V640" fill="none" stroke="rgba(210,153,34,.5)" strokeWidth="2" className="ahc-trace-slow" />

      {/* 未启用芯片：走线断开（灰） */}
      {chips
        .filter((chip) => !chip.enabled)
        .map((chip, i) => (
          <path
            key={`off-${chip.y}`}
            d={`M640 448 H${760 + i * 20} V${chip.y + 42} H850`}
            fill="none"
            stroke="rgba(148,163,184,.16)"
            strokeWidth="1.6"
            strokeDasharray="2 8"
          />
        ))}

      {/* 晶振 → 主控 */}
      <path d="M610 529 V505 H640" fill="none" stroke="rgba(148,163,184,.4)" strokeWidth="1.2" className="ahc-trace-clk" />

      {/* 信号丝印 */}
      <g fontSize="8" letterSpacing="1" style={{ fontFamily: 'inherit' }} className="ahc-mono">
        <text x="212" y="162" fill="rgba(168,85,247,.6)">KB-READ</text>
        <text x="222" y="266" fill="rgba(88,166,255,.55)">NEWS</text>
        <text x="232" y="329" fill="rgba(244,114,182,.5)">SENT</text>
        {firstLive && <text x="690" y="348" fill="rgba(103,232,249,.75)">PLAN·WATCH</text>}
        {firstOrder && <text x="946" y="232" fill="rgba(248,81,73,.75)">ORDER</text>}
        <text x="478" y="600" fill="rgba(210,153,34,.6)">CRON</text>
        <text x="648" y="532" fill="rgba(148,163,184,.5)">CLK</text>
      </g>

      {/* 过孔 */}
      <g fill={BOARD.bg} strokeWidth="1.6">
        <circle cx="300" cy="170" r="4" stroke="rgba(168,85,247,.6)" />
        <circle cx="340" cy="274" r="4" stroke="rgba(88,166,255,.55)" />
        <circle cx="360" cy="337" r="4" stroke="rgba(244,114,182,.5)" />
        <circle cx="535" cy="560" r="4" stroke="rgba(210,153,34,.6)" />
        {liveChips.map((chip, i) => (
          <circle key={`via-${chip.y}`} cx={700 + i * 30} cy={chip.y + 54} r="4.5" stroke={chip.accent} strokeOpacity=".85" />
        ))}
      </g>

      {/* 电子脉冲（reduced-motion 时整体关闭） */}
      {!reducedMotion && (
        <g>
          {firstLive && (
            <>
              <circle r="3" fill={BOARD.cyanSoft}>
                <animateMotion dur="1.7s" repeatCount="indefinite" path={`M640 356 H760 V${firstLive.y + 54} H820`} />
              </circle>
              <circle r="2.2" fill="rgba(103,232,249,.8)">
                <animateMotion dur="1.7s" begin="0.55s" repeatCount="indefinite" path={`M640 356 H760 V${firstLive.y + 54} H820`} />
              </circle>
            </>
          )}
          <circle r="2.6" fill={BOARD.purpleSoft}>
            <animateMotion dur="4.8s" repeatCount="indefinite" path="M170 170 H300 V356 H430" />
          </circle>
          <circle r="2.2" fill={BOARD.blueSoft}>
            <animateMotion dur="4.4s" repeatCount="indefinite" path="M170 274 H340 V400 H430" />
          </circle>
          {firstOrder && (
            <circle r="2.4" fill={BOARD.redSoft}>
              <animateMotion dur="1.4s" repeatCount="indefinite" path={`M940 ${firstOrder.y + 54} H1000 V376 H1010`} />
            </circle>
          )}
          <circle r="2.2" fill={BOARD.amberSoft}>
            <animateMotion dur="4.2s" repeatCount="indefinite" path="M535 484 V560 H520 V640" />
          </circle>
        </g>
      )}
    </g>
  )
}
