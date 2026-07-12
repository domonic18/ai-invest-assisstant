# AI Invest Assistant Backend - Claude Code AI 上下文文件

> 本目录下的规则是对项目根目录 [CLAUDE.md](../CLAUDE.md) 通用规则的补充。请先阅读根目录的通用规则。

## 1. 技术栈

- **Python**: 3.10+
- **Web 框架**: FastAPI 0.111+ / Uvicorn
- **ORM**: SQLAlchemy 2.0+ / Alembic
- **数据验证**: Pydantic 2.7+ / Pydantic Settings
- **AI Agent**: PydanticAI 2.x / OpenAI SDK / Anthropic SDK
- **MCP**: mcp 1.x
- **配置管理**: Pydantic Settings + YAML 配置文件
- **日志**: structlog
- **测试**: pytest

## 2. Python 编码规范

### 类型提示（必需）

- **始终**为函数参数和返回值使用类型提示
- 对复杂类型使用 `from typing import` 或 `collections.abc`
- 优先使用 `Optional[T]` 而不是 `Union[T, None]`
- 对数据结构使用 Pydantic 模型

```python
# 良好示例
from typing import Optional, Dict, Any
from collections.abc import AsyncIterator

async def get_stock_metrics(
    code: str,
    start_date: datetime,
    end_date: datetime,
    include_cache: bool = True,
) -> Optional[Dict[str, Any]]:
    """获取股票指标数据。"""
    pass
```

### 命名约定

| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | `BaseCollector`, `StockService` |
| 函数/方法 | snake_case | `fetch_kline`, `calculate_metrics` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_PAGE_SIZE` |
| 私有方法 | 前导下划线 | `_validate_input` |
| Pydantic 模型 | PascalCase | `StockResponse` |
| 数据库模型 | PascalCase | `Stock`, `KLine` |
| API 端点 | snake_case | `get_stock_detail` |

### 文档要求

- 每个模块需要文档字符串
- 每个公共函数需要文档字符串
- 使用 Google 风格的文档字符串
- 在文档字符串中包含类型信息

```python
async def fetch_kline(
    self,
    params: Optional[Dict[str, Any]] = None,
) -> CollectorResult[List[KLine]]:
    """采集 K 线数据。

    Args:
        params: 采集参数，包含时间范围等筛选条件

    Returns:
        采集结果，包含 K 线数据列表和采集元信息

    Raises:
        CollectorConnectionError: 网络连接失败
        CollectorAuthenticationError: 认证失败
        CollectorRateLimitError: API 限流
    """
    pass
```

## 3. 架构规范

### 薄路由、重服务的分层架构

- 路由层只处理 HTTP 逻辑（参数验证、响应格式、状态码、异常转换）
- 业务逻辑在服务层实现
- 正确使用 HTTP 状态码
- 使用一致的 JSON 响应格式
- 列表端点支持分页

### AI Agent 与 Prompt 管理

- 所有 Agent Prompt 必须放在 `app/prompts/agents/` 和 `app/prompts/skills/` 下的 YAML 文件中
- 禁止在 Python 代码中硬编码 Prompt
- 使用 `PromptLoader` / `SkillLoader` 加载配置
- 使用 `llm_router.build_model()` / `build_agent()` 统一创建模型与 Agent

### 可观测系统与日志标准

- 使用 structlog 进行结构化日志记录
- 日志按模块分离：app logs, collector logs
- 为机器而不是人类构建日志 - 使用 JSON 格式，带一致字段（时间戳、级别、事件、上下文）

### 状态管理

- 每个状态片段有一个真相来源
- 让状态变更明确且可追踪
- 缓存失效策略要明确

## 4. 开发工具链

**统一使用 `uv`（不是 pip/python3）**：

```bash
# 运行 FastAPI 服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 运行测试
uv run pytest
uv run pytest -m unit
uv run pytest -xvs tests/unit/test_example.py

# 类型检查
uv run mypy app/

# 代码 lint
uv run ruff check .
uv run ruff check --fix .

# 同步依赖
uv sync

# 添加依赖
uv add <package>

# 添加开发依赖
uv add --group dev <package>
```

## 5. 测试规范

测试标记：

- `unit`: 单元测试，无外部依赖，快速执行
- `integration`: 集成测试，需要数据库/Redis/ES 等中间件
- `database`: 数据库测试
- `collector`: 采集器测试
- `api`: API 接口测试
- `mcp`: MCP 接口测试

## 6. 任务完成后检查清单

完成后端编码任务后：

1. **类型安全**：`uv run mypy app/`
2. **测试**：`uv run pytest -m unit`
3. **代码质量**：`uv run ruff check .`
4. **验证**：API 端点的输入验证和错误处理
5. **文档**：确保代码注释和文档字符串保持最新
