import { createContext, useContext } from 'react'

interface SuggestedQuestionContextValue {
  /** 从建议芯片或外部入口发送一条用户问题。 */
  sendQuestion: (question: string) => void
}

export const SuggestedQuestionContext = createContext<SuggestedQuestionContextValue>({
  sendQuestion: () => {},
})

export function useSuggestedQuestion(): (question: string) => void {
  return useContext(SuggestedQuestionContext).sendQuestion
}
