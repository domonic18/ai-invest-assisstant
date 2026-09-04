import { MessagePrimitive } from '@assistant-ui/react'

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="mb-5 flex justify-end gap-3">
      <div className="max-w-[85%] space-y-1">
        <div className="whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2.5 text-sm text-white shadow-sm">
          <MessagePrimitive.Content />
        </div>
      </div>
    </MessagePrimitive.Root>
  )
}
