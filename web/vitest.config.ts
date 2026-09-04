import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'
import { readFileSync } from 'fs'

const pkg = JSON.parse(readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'))

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    exclude: ['node_modules', 'dist', 'e2e', '**/*.e2e.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'cobertura', 'html'],
      reportsDirectory: './report/coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/**/*.d.ts',
        'src/test/**',
        'src/**/*.type.ts',
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
