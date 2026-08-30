# 测试体系设计

## 1. 设计目标

- 保证数据层、后端 API、前端页面、采集任务、AI Skill 在迭代过程中稳定可用。
- 通过分层测试快速定位问题：单元测试验证局部逻辑，集成测试验证模块协作，端到端测试验证核心用户链路。
- 参考 SquadSight 项目实践，建立独立的 `qa/` 目录承载黑盒集成测试，`backend/tests/` 承载白盒单元/集成测试，`web/` 承载前端单元与 E2E 测试。

## 2. 测试分层

```
┌─────────────────────────────────────────────────────────────┐
│                    测试金字塔                                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         E2E 测试（Playwright）                         │  │
│  │    登录 → 仪表盘 → 产业链分析 → 个股详情               │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         集成测试（pytest + httpx / TestClient）        │  │
│  │    API 接口、数据库、Redis、ES、COS 协作               │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         单元测试（pytest / Vitest）                    │  │
│  │    Service、Schema、采集器、Agent、Hooks、Utils       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 3. 后端测试

### 3.1 目录结构

```
backend/
├── app/                              # 业务代码
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # 共享 fixtures（TestClient 封装 + mock session）
│   ├── unit/                         # 单元测试（无外部依赖，全部 mock）
│   │   ├── agent/                    # 运行时组装 / wire 序列化 / subagents / skills
│   │   ├── api/                      # 协议端点 / admin 接口
│   │   ├── collector/                # 采集器 / registry / celery 队列
│   │   ├── services/                 # 服务层业务逻辑
│   │   ├── test_crypto.py
│   │   └── test_llm_config_service.py
│   └── integration/                  # 集成测试（需中间件）
├── pyproject.toml                      # uv 依赖与工具配置
└── uv.lock                             # 依赖锁定文件
```

### 3.2 技术栈

| 类型 | 工具 | 用途 |
|------|------|------|
| 包管理 | uv | Python 依赖与虚拟环境 |
| 测试框架 | pytest + pytest-asyncio | 单元/集成测试 |
| HTTP 客户端 | httpx / TestClient | API 接口测试 |
| 数据隔离 | mock session（覆盖 `get_db`） | 单元测试不落库，仓储/服务协作全 mock |
| 异步 | pytest-asyncio | 协程测试 |
| Mock | unittest.mock / pytest-mock / respx | 外部 HTTP/ES 模拟 |
| 覆盖率 | pytest-cov | 覆盖率统计 |

### 3.3 测试标记

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
markers =
    unit: 单元测试，无外部依赖，快速执行
    integration: 集成测试，需要数据库/Redis/ES等中间件
    database: 数据库测试
    collector: 采集器测试
    api: API 接口测试
    mcp: MCP 接口测试
```

### 3.4 关键 Fixtures

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.main import app


@pytest.fixture
def client():
    """返回已清除依赖覆盖的 TestClient。"""
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


class _MockSession:
    """极简 mock session，用于覆盖 get_db。"""

    async def commit(self) -> None: ...
    async def refresh(self, obj: object) -> None: ...
    async def close(self) -> None: ...


@pytest.fixture
def mock_session(client):
    """覆盖 get_db 返回一个 mock session（单元测试不落库）。"""
    session = _MockSession()

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    return session
```

> 单元测试以 mock 为主（外部 HTTP、session、LLM 均不打真实端点）；涉及真实 PG/Redis/ES 的路径归入 `integration/` 与 `qa/`。

### 3.5 单元测试示例

```python
# tests/unit/services/test_stock_service.py
import pytest
from app.services.stock_service import StockService


class TestStockService:
    @pytest.mark.unit
    def test_normalize_stock_code(self):
        assert StockService.normalize_code("000001") == "000001.SZ"
        assert StockService.normalize_code("600000") == "600000.SH"

    @pytest.mark.unit
    def test_calculate_change_pct(self):
        assert StockService.calculate_change_pct(110, 100) == 10.0
```

### 3.6 集成测试示例

```python
# tests/integration/api/test_auth_api.py
import pytest


@pytest.mark.integration
@pytest.mark.api
class TestAuthAPI:
    def test_register_and_login(self, client):
        # 注册
        r = client.post("/api/v1/auth/register", json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "Test1234!"
        })
        assert r.status_code == 201

        # 登录
        r = client.post("/api/v1/auth/login", json={
            "username": "tester",
            "password": "Test1234!"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()
```

## 4. 前端测试（Web）

### 4.1 目录结构

```
web/
├── src/
│   ├── test/
│   │   └── setup.ts                  # 测试环境初始化
│   ├── components/
│   │   └── charts/
│   │       └── __tests__/
│   │           └── KlineChart.test.tsx
│   ├── hooks/
│   │   └── __tests__/
│   │       └── useAuth.test.ts
│   ├── utils/
│   │   └── __tests__/
│   │       └── formatters.test.ts
│   └── pages/
│       └── Dashboard/
│           └── __tests__/
│               └── Dashboard.test.tsx
├── vitest.config.ts
└── playwright.config.ts
```

### 4.2 技术栈

| 类型 | 工具 | 用途 |
|------|------|------|
| 单元测试 | Vitest + jsdom | 组件、Hooks、Utils |
| 组件测试 | @testing-library/react | DOM 交互断言 |
| E2E 测试 | Playwright | 核心用户链路 |
| Mock | MSW (Mock Service Worker) | API 请求模拟 |
| 覆盖率 | @vitest/coverage-v8 | 覆盖率统计 |

### 4.3 Vitest 配置

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
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
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

### 4.4 Playwright E2E 配置

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
```

### 4.5 E2E 核心链路

```
登录页 → 仪表盘 → 产业链分析 → 个股详情 → 用户设置
```

## 5. 集成/QA 测试

参考 SquadSight，建立独立的 `qa/` 目录，用于对部署后的环境进行黑盒接口测试。

### 5.1 目录结构

```
qa/                                  # 独立 uv 项目
├── pyproject.toml                   # uv 依赖配置
└── integration/                     # 黑盒集成测试
    ├── conftest.py                  # 环境变量、fixtures、资源清理
    ├── test_auth.py
    ├── test_collector.py
    └── test_health.py
```

### 5.2 环境变量

```bash
export QA_BASE_URL="https://api.your-domain.com"
export QA_ADMIN_USERNAME="admin"
export QA_ADMIN_PASSWORD="xxx"
```

### 5.3 测试示例

```python
# qa/integration/test_stocks.py
import pytest


@pytest.mark.integration
@pytest.mark.api
class TestStocks:
    def test_search_stock(self, client, auth_headers):
        r = client.get(
            f"{base_url}/api/v1/stocks/search",
            params={"q": "平安"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) > 0
```

## 6. 采集任务测试

### 6.1 测试策略

- **单元测试**：验证 `BaseCollector` 模板方法、数据清洗管道、反爬中间件。
- **Mock 外部请求**：使用 `respx` / `pytest-httpx` 模拟同花顺、东方财富、巨潮资讯接口返回。
- **集成测试**：在本地启动测试容器，执行一次完整采集任务并校验入库结果。

### 6.2 示例

```python
# backend/tests/unit/collector/test_limit_up_ai_review.py（节选）
import pytest
from collector.spiders.limit_up_ai_review import LimitUpAiReviewCollector


@pytest.mark.unit
@pytest.mark.collector
class TestLimitUpAiReviewCollector:
    async def test_cached_hit_skipped(self, monkeypatch):
        # 缓存命中 → SKIPPED（良性终态，不触发 LLM，不轮换渠道）
        ...
```

## 7. Skill 测试

### 7.1 测试目标

- 验证 Skill 输入解析正确。
- 验证 Skill 输出 JSON 符合预定义 Schema。
- 建立输出样例库，用于回归测试。

### 7.2 测试方式

```python
# backend/tests/unit/services/test_chain_service.py
import pytest
from app.services.chain_service import parse_chain_skill_output


@pytest.mark.unit
class TestChainSkillOutput:
    def test_valid_json_parsing(self):
        raw = '{"industry": "半导体", "nodes": []}'
        result = parse_chain_skill_output(raw)
        assert result["industry"] == "半导体"

    def test_invalid_json_fallback(self):
        raw = '```json\n{"industry": "半导体"}\n```'
        result = parse_chain_skill_output(raw)
        assert result["industry"] == "半导体"
```

## 8. 移动端测试

### 8.1 技术栈

| 类型 | 工具 | 用途 |
|------|------|------|
| 视口测试 | Playwright + 视口预设 | 桌面 / 平板 / 移动断点 |
| 真机预览 | 浏览器 DevTools 设备模拟 | 底部 Tab Bar、抽屉导航、双指缩放 |

### 8.2 测试重点

- 桌面 / 移动布局切换（底部 Tab Bar 在 ≤768px 出现）
- 产业链图谱双指缩放与节点点击
- 表格在小屏的可读性（横向滚动 vs 折叠详情）

## 9. CI/CD 集成

### 9.1 GitHub Actions 工作流（`.github/workflows/ci.yml`）

| Job | 触发 | 内容 |
|-----|------|------|
| Backend | push / PR / 手动 | uv 同步依赖 → `ruff check` → `mypy` → `pytest -m unit` |
| Web | push / PR / 手动 | 构建 shared 包 → npm 安装 → lint → typecheck → 单测 |
| Docker | push develop / main | buildx 构建 amd64 双镜像（web-api / collector）→ 推送 TCR（secrets：`TCR_NAMESPACE` / `TCR_USERNAME` / `TCR_PASSWORD`） |

### 9.2 测试阶段

| 阶段 | 触发条件 | 测试范围 |
|------|----------|----------|
| 本地开发 | 每次保存 | 相关单元测试 |
| Pull Request | CI 自动 | 全量单元测试 + 前端构建 |
| 合并后 | CI 自动 | 单元测试 + 集成测试 |
| 部署前 | 手动/定时 | qa/ 黑盒集成测试 |

## 10. 覆盖率与质量门禁

| 层级 | 目标覆盖率 | 说明 |
|------|-----------|------|
| 后端 Service 层 | ≥ 70% | 核心计算逻辑必须覆盖 |
| 后端 API 层 | ≥ 60% | P0/P1 接口覆盖 |
| 采集器 | ≥ 50% | transform/validate 逻辑覆盖 |
| 前端 Utils/Hooks | ≥ 60% | 工具函数、状态管理 |
| 前端组件 | ≥ 40% | 关键图表组件 |
| E2E | 核心链路 100% | 登录 → 仪表盘 → 产业链 → 个股 |

## 11. 测试数据管理

### 11.1 种子数据

- `docker/database/init-scripts/03-seed.sql` 提供测试用股票、用户、行情数据。
- 测试环境独立：单元测试使用内存 SQLite；集成测试使用 Docker Compose 启动的测试中间件。

### 11.2 Mock 数据

- 采集器原始响应样本、Skill 输出样例内联在对应单测文件中维护（必要时抽到 `backend/tests/fixtures/`）。
- `web/src/test/`：测试环境初始化与 API 响应模拟数据。

## 12. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [05-web-frontend.md](./05-web-frontend.md) — Web 前端架构
- [06-deployment.md](./06-deployment.md) — 部署架构与运维
