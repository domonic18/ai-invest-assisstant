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
│  │    API 接口、数据库、Redis、ES、Milvus、MinIO 协作     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         单元测试（pytest / Vitest）                    │  │
│  │    Service、Schema、Pipeline、Hooks、Utils            │  │
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
│   ├── conftest.py                   # 共享 fixtures、标记、数据库配置
│   ├── unit/                         # 单元测试
│   │   ├── services/
│   │   │   ├── test_stock_service.py
│   │   │   ├── test_chain_service.py
│   │   │   └── test_auth_service.py
│   │   ├── collectors/
│   │   │   ├── test_base_collector.py
│   │   │   └── test_cninfo_collector.py
│   │   ├── pipelines/
│   │   │   └── test_data_pipeline.py
│   │   └── schemas/
│   │       └── test_api_schemas.py
│   └── integration/                  # 集成测试
│       ├── api/
│       │   ├── test_auth_api.py
│       │   ├── test_stocks_api.py
│       │   └── test_chain_api.py
│       ├── db/
│       │   └── test_timescale_hypertable.py
│       └── mcp/
│           └── test_mcp_server.py
├── pytest.ini
├── pyproject.toml                      # uv 依赖与工具配置
└── uv.lock                             # 依赖锁定文件
```

### 3.2 技术栈

| 类型 | 工具 | 用途 |
|------|------|------|
| 包管理 | uv | Python 依赖与虚拟环境 |
| 测试框架 | pytest + pytest-asyncio | 单元/集成测试 |
| HTTP 客户端 | httpx / TestClient | API 接口测试 |
| 数据库 | SQLite + aiosqlite（内存模式） | 集成测试隔离数据库 |
| 异步 | pytest-asyncio | 协程测试 |
| Mock | unittest.mock / pytest-mock / respx | 外部 HTTP/Milvus/ES 模拟 |
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
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# 内存 SQLite，StaticPool 保证多协程共享同一连接
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """为 session 级 async fixture 提供统一事件循环。"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session):
    """依赖 db_session 的 TestClient。"""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_milvus(mocker):
    """模拟 Milvus 向量搜索结果。"""
    return mocker.patch("app.services.chain_service.search_milvus", return_value=[])
```

### 3.5 PostgreSQL → SQLite 兼容补丁

集成测试使用 SQLite 内存数据库，需对 PostgreSQL 特有类型打补丁：

```python
# tests/conftest.py
def _patch_postgresql_types_for_sqlite():
    from sqlalchemy import JSON, Text
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.ext.compiler import compiles

    @compiles(postgresql.JSONB, 'sqlite')
    def compile_jsonb_sqlite(element, compiler, **kw):
        return compiler.process(JSON(), **kw)

    @compiles(postgresql.ARRAY, 'sqlite')
    def compile_array_sqlite(element, compiler, **kw):
        return compiler.process(Text(), **kw)
```

### 3.6 单元测试示例

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

### 3.7 集成测试示例

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
qa/
├── conftest.py                       # 环境变量、fixtures、资源清理
├── pyproject.toml                    # uv 依赖配置
└── integration/                      # 黑盒集成测试
    ├── test_auth.py
    ├── test_stocks.py
    ├── test_chain.py
    ├── test_auction.py
    ├── test_hotspot.py
    └── test_mcp.py
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
# backend/tests/unit/collectors/test_cninfo_collector.py
import pytest
from collector.spiders.cninfo import CninfoCollector


@pytest.mark.unit
@pytest.mark.collector
class TestCninfoCollector:
    @pytest.fixture
    def collector(self):
        return CninfoCollector({"source": "cninfo", "data_type": "announcement"})

    async def test_transform(self, collector):
        raw = {"announcementId": "123", "announcementTitle": "年度报告"}
        item = await collector.transform(raw)
        assert item["title"] == "年度报告"
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

## 8. 小程序测试

### 8.1 技术栈

| 类型 | 工具 | 用途 |
|------|------|------|
| 单元测试 | Vitest + jsdom | Hooks、Utils |
| 组件测试 | @testing-library/react | Taro 组件渲染 |
| 真机/模拟器测试 | 微信开发者工具 | 真机预览、自动化测试 |

### 8.2 测试重点

- 自选股列表渲染与价格格式化。
- 集合竞价曲线组件数据转换。
- 微信登录流程与 Token 管理。

## 9. CI/CD 集成

### 9.1 GitHub Actions 工作流

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Sync dependencies
        run: cd backend && uv sync
      - name: Run unit tests
        run: cd backend && uv run pytest -m unit --cov=app --cov-report=xml

  web-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd web && npm install
      - run: cd web && npm run lint
      - run: cd web && npm run typecheck
      - run: cd web && npm run test:unit -- --coverage
```

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

- `backend/tests/fixtures/`：存放采集器原始响应样本、Skill 输出样例。
- `web/src/test/mocks/`：MSW handler 与 API 响应模拟数据。

## 12. 后续文档索引

- [00-overview.md](./00-overview.md) — 总体架构与目录结构
- [05-web-frontend.md](./05-web-frontend.md) — Web + 小程序前端架构
- [06-deployment.md](./06-deployment.md) — 部署与运维方案
- [../plan/development-plan.md](../plan/development-plan.md) — 开发计划与里程碑
