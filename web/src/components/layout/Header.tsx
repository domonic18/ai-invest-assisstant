import { Link } from 'react-router-dom'

export function Header() {
  return (
    <header className="h-14 border-b border-gray-800 flex items-center px-6 justify-between bg-gray-900">
      <h1 className="text-lg font-semibold">AI Invest Assistant</h1>
      <div className="flex gap-4">
        <Link to="/settings" className="text-sm text-gray-400 hover:text-white">设置</Link>
      </div>
    </header>
  )
}
