import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp, ConfigProvider, theme } from 'antd'
import { useEffect } from 'react'
import { RouterProvider } from 'react-router-dom'

import { router } from './router'
import { useAuthStore } from './stores/auth'

import { useSettingsStore } from './stores/settings'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function AuthInitializer() {
  const initialize = useAuthStore((state) => state.initialize)
  const token = useAuthStore((state) => state.token)
  const initSettings = useSettingsStore((state) => state.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  useEffect(() => {
    if (token) {
      initSettings()
    }
  }, [token, initSettings])

  return null
}

export default function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        components: {
          Segmented: {
            trackBg: '#0c0e12',
            itemSelectedBg: '#2a2e38',
            itemHoverBg: 'rgba(255,255,255,0.06)',
          },
        },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <AuthInitializer />
          <RouterProvider router={router} />
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  )
}
