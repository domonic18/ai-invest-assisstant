import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['antd', '@ant-design/icons'],
          charts: ['echarts', 'echarts-for-react', '@antv/g6'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
      '/docs': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
    },
  },
})
