import { RobotOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useLocation } from 'react-router-dom'

import { useSuggestedQuestion } from './SuggestedQuestionContext'
import { SuggestedChips } from './ui/SuggestedChips'

const DEFAULT_QUESTIONS = [
  '平安银行最近走势如何？',
  '帮我做一次半导体产业链体检',
  '今天大盘资金流向有什么特点？',
  '宁德时代最新财务指标怎么样？',
  '近期有哪些热点板块？',
  '宁德时代近期新闻情绪如何？',
]

function routeToQuestion(pathname: string): string | null {
  const stockMatch = pathname.match(/\/stock\/([^/]+)/)
  if (stockMatch) {
    return `${stockMatch[1]} 最近走势如何？`
  }
  const chainMatch = pathname.match(/\/chain\/([^/]+)/)
  if (chainMatch) {
    return `帮我做一次 ${decodeURIComponent(chainMatch[1])} 产业链体检`
  }
  return null
}

export function AssistantEmptyState() {
  const location = useLocation()
  const sendQuestion = useSuggestedQuestion()
  const contextual = routeToQuestion(location.pathname)
  const questions = contextual
    ? [contextual, ...DEFAULT_QUESTIONS.slice(0, 5)]
    : DEFAULT_QUESTIONS

  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600/20">
        <RobotOutlined className="text-2xl text-blue-400" />
      </div>
      <h3 className="mb-1 text-base font-medium text-white">AI 投研助手</h3>
      <p className="mb-6 max-w-sm text-sm text-gray-400">
        支持行情、财务、资金流、竞价、新闻、研报等投研问答。我可以帮你分析个股、产业链、市场热点。
      </p>
      <div className="w-full max-w-sm text-left">
        <div className="mb-2 flex items-center gap-1.5 text-xs text-gray-500">
          <ThunderboltOutlined />
          试试这样问
        </div>
        <SuggestedChips questions={questions} onSelect={sendQuestion} />
      </div>
    </div>
  )
}
