import type { TodoStep } from '@/stores/assistant'

const TODO_MARKERS: Record<TodoStep['status'], string> = {
  completed: '✓',
  in_progress: '◐',
  pending: '○',
}

export function TodoListBar({ todos }: { todos: TodoStep[] }) {
  return (
    <div className="border-b border-gray-800 px-4 py-2">
      <div className="mb-1 text-xs text-gray-500">执行计划</div>
      <ol className="space-y-1">
        {todos.map((todo, index) => (
          <li
            key={index}
            className={`flex items-start gap-2 text-xs ${
              todo.status === 'in_progress'
                ? 'text-blue-300'
                : todo.status === 'completed'
                  ? 'text-gray-500'
                  : 'text-gray-400'
            }`}
          >
            <span
              className={`w-4 shrink-0 text-center ${
                todo.status === 'in_progress' ? 'animate-pulse' : ''
              }`}
            >
              {TODO_MARKERS[todo.status]}
            </span>
            <span className={todo.status === 'completed' ? 'line-through' : ''}>
              {todo.content}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
