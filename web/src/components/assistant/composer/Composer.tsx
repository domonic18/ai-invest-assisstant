import {
  ComposerPrimitive,
  ThreadPrimitive,
  unstable_useComposerInput,
} from '@assistant-ui/react'
import { useEffect } from 'react'

interface ComposerProps {
  /** 注册一个可由外部（如建议问题）调用的发送回调。 */
  registerSend?: (send: (question: string) => void) => void
}

export function Composer({ registerSend }: ComposerProps) {
  const composer = unstable_useComposerInput()

  useEffect(() => {
    registerSend?.((question) => {
      composer.setText(question)
      composer.send()
    })
  }, [composer, registerSend])

  return (
    <ComposerPrimitive.Root className="border-t border-gray-800 bg-[#0c0e12] p-3">
      <div className="relative flex items-end gap-2 rounded-xl border border-gray-700 bg-gray-900 p-2 shadow-sm transition-colors focus-within:border-blue-500/60">
        <ComposerPrimitive.Input
          rows={1}
          autoFocus
          placeholder="问我任何投研问题，如「平安银行最近走势如何」"
          className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none"
        />
        <div className="flex shrink-0 items-center gap-1 pb-1 pr-1">
          <ThreadPrimitive.If running>
            <ComposerPrimitive.Cancel className="rounded-lg border border-red-700 bg-red-900/40 px-3 py-1.5 text-sm text-red-300 hover:bg-red-900/70">
              停止
            </ComposerPrimitive.Cancel>
          </ThreadPrimitive.If>
          <ThreadPrimitive.If running={false}>
            <ComposerPrimitive.Send className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-500 disabled:opacity-40">
              发送
            </ComposerPrimitive.Send>
          </ThreadPrimitive.If>
        </div>
      </div>
    </ComposerPrimitive.Root>
  )
}
