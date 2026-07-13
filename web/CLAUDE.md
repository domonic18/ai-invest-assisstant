# AI Invest Assistant Web - Claude Code AI 上下文文件

> 本目录下的规则是对项目根目录 [CLAUDE.md](../CLAUDE.md) 通用规则的补充。请先阅读根目录的通用规则。

## 1. 技术栈

- **框架**: React 18.3+
- **语言**: TypeScript 5.4+
- **构建工具**: Vite 5.2+
- **路由**: React Router 6.23+
- **状态管理**: Zustand
- **数据获取**: TanStack Query (React Query)
- **UI 组件库**: Ant Design 5
- **样式**: Tailwind CSS（用于自定义布局与 Ant Design 未覆盖的微调）
- **图表**: ECharts + echarts-for-react, AntV/G6, D3
- **HTTP 客户端**: axios
- **测试**: Vitest + React Testing Library + Playwright (E2E)

## 2. 开发命令

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 生产构建
npm run build

# 类型检查
npm run typecheck

# 运行 lint
npm run lint

# 运行单元测试
npm run test:unit

# 运行 E2E 测试
npm run test:e2e
```

## 3. 目录结构约定

```
src/
├── api/           # API 客户端与请求函数
├── components/    # 可复用 UI 组件
├── hooks/         # 自定义 React Hooks
├── pages/         # 页面级组件
├── router.tsx     # 路由配置
├── stores/        # Zustand 状态管理
├── types/         # TypeScript 类型定义
└── utils/         # 工具函数
```

## 4. 编码规范

### TypeScript

- 为所有组件 props、函数参数和返回值提供类型
- 优先使用接口（interface）定义对象类型
- 避免使用 `any`，如必须使用时添加注释说明原因
- 使用路径别名 `@/` 引用 `src/` 下的模块

### React

- 函数组件优先，使用 React Hooks
- 组件文件名使用 PascalCase
- 自定义 Hook 文件名以 `use` 开头
- 避免在渲染阶段产生副作用

### 样式

- 优先使用 **Ant Design 5** 组件与 Design Token，保持界面一致性。
- Tailwind CSS 用于页面级布局、间距、响应式微调以及 Ant Design 未覆盖的自定义样式。
- 复杂样式可提取为独立 CSS 文件。
- 主题颜色通过 Ant Design ConfigProvider + Tailwind 配置统一管理。

## 5. 任务完成后检查清单

完成前端编码任务后：

1. **类型检查**：`npm run typecheck`
2. **构建验证**：`npm run build`
3. **代码质量**：`npm run lint`
4. **测试**：`npm run test:unit`
5. **验证**：在浏览器中测试功能正常
