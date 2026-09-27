/**
 * 「AI 画线」入口按钮：打开侧边栏助手并预置画线问句（kline-smart-drawing
 * skill 由助手按 SKILL.md 流程执行：检查已有画线 → 确认 → 取数 → 落图）。
 */

import { ExperimentOutlined } from '@ant-design/icons'

import { useAssistantStore } from '@/stores/assistant'

export const AI_DRAWING_QUESTION = '帮我画出当前标的的关键压力/支撑与形态边界（AI 画线）'

export function AiDrawingButton() {
  const sendQuestion = useAssistantStore((state) => state.sendQuestion)
  return (
    <button
      type="button"
      className="inline-flex shrink-0 items-center gap-1 px-2.5 py-[3px] text-xs whitespace-nowrap rounded transition-colors text-[#8a8f98] hover:text-[#8a93ff]"
      title="AI 分析关键压力/支撑与形态边界并画到图上"
      onClick={() => sendQuestion(AI_DRAWING_QUESTION)}
    >
      <ExperimentOutlined style={{ fontSize: 11 }} />
      AI 画线
    </button>
  )
}
