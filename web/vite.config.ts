import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// 版本号来源：环境变量 > 根目录 VERSION 文件 > 默认值
const versionFile = path.resolve(__dirname, '../VERSION')
const appVersion = process.env.VITE_APP_VERSION
  || (fs.existsSync(versionFile)
    ? fs.readFileSync(versionFile, 'utf-8').trim()
    : '0.1.0')

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
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
