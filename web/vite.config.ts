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
    // hidden：产物生成 .map 但 HTML 不引用（线上不暴露），排障时用本地 map 还原堆栈
    sourcemap: 'hidden',
    rollupOptions: {
      output: {
        // 函数式按包路由（object 形式对仅经动态导入可达的 g6 不生效）：
        // g6 独立分包（v4 单体不可摇树，~1.5MB）仅产业链图消费，其余图表页
        // 不必连带下载；@antv/* 全家桶仅 g6 使用，可整族归并
        manualChunks(id: string) {
          if (id.includes('node_modules/@antv/')) return 'g6'
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) return 'charts'
          if (id.includes('node_modules/antd') || id.includes('node_modules/@ant-design/')) return 'ui'
          if (
            id.includes('node_modules/react/')
            || id.includes('node_modules/react-dom/')
            || id.includes('node_modules/react-router')
          ) {
            return 'vendor'
          }
          return undefined
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
