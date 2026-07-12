import { Link } from 'react-router-dom'

const navItems = [
  { path: '/', label: '仪表盘' },
  { path: '/chain', label: '产业链分析' },
  { path: '/hotspot', label: '热点追踪' },
  { path: '/capital-flow', label: '资金流向' },
  { path: '/auction', label: '集合竞价' },
  { path: '/research', label: '研报中心' },
  { path: '/admin', label: '后台管理' },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r border-gray-800 bg-gray-900 flex flex-col">
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className="block px-3 py-2 rounded text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
