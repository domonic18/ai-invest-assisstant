/**
 * ask_user 问题卡（arch/09 §7.3）：渲染在输入框上方，选项点击即作为
 * 用户消息续跑对话（`我选择：{label}`），同时清空卡片。
 */

import { CloseOutlined } from '@ant-design/icons'

import { useAssistantStore } from '@/stores/assistant'

export function QuestionCard() {
  const questionCard = useAssistantStore((state) => state.questionCard)
  const setQuestionCard = useAssistantStore((state) => state.setQuestionCard)
  const sendQuestion = useAssistantStore((state) => state.sendQuestion)
  if (!questionCard) return null

  return (
    <div className="mx-4 mb-2 rounded-lg border border-[#5e6ad2]/45 bg-[#151824]/95 p-3 shadow-lg">
      <div className="flex items-start justify-between gap-2">
        <p className="m-0 text-[13px] leading-5 text-[#c9cdd4]">{questionCard.question}</p>
        <button
          type="button"
          aria-label="关闭问题卡"
          className="shrink-0 border-none bg-transparent p-0 text-xs text-[#6b7280] hover:text-[#9aa0aa]"
          onClick={() => setQuestionCard(null)}
        >
          <CloseOutlined />
        </button>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {questionCard.options.map((option) => {
          const recommended = questionCard.default === option.value
          return (
            <button
              key={option.value}
              type="button"
              className="rounded-md border px-2.5 py-1 text-xs transition-colors"
              style={{
                borderColor: recommended ? '#5e6ad2' : 'rgba(255,255,255,0.14)',
                color: recommended ? '#aeb4ff' : '#c9cdd4',
                background: recommended ? 'rgba(94,106,210,0.16)' : 'transparent',
              }}
              onClick={() => sendQuestion(`我选择：${option.label}`)}
            >
              {option.label}
              {recommended ? '（推荐）' : ''}
            </button>
          )
        })}
      </div>
    </div>
  )
}
