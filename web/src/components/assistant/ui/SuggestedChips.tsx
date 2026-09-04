import { ThunderboltOutlined } from '@ant-design/icons'

interface SuggestedChipsProps {
  questions: string[]
  onSelect: (question: string) => void
}

/** 空会话或助手消息底部的建议问题芯片。 */
export function SuggestedChips({ questions, onSelect }: SuggestedChipsProps) {
  if (!questions.length) return null

  return (
    <div className="flex flex-wrap gap-2">
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onSelect(q)}
          className="flex items-center gap-1.5 rounded-full border border-gray-700 bg-gray-800/60 px-3 py-1.5 text-xs text-gray-300 transition-colors hover:border-blue-500/60 hover:bg-blue-500/10 hover:text-blue-200"
        >
          <ThunderboltOutlined />
          {q}
        </button>
      ))}
    </div>
  )
}
