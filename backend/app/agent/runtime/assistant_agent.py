"""对话助手 deepagents 运行时组装（按模型出口指纹的 LRU 缓存）。

- 模型：``resolve_llm`` 解析出口——BYOK 用户各自独立 agent 实例，
  系统默认模型全站共享一个；llm_config 变更后指纹变化自然重建
- 系统提示词：``prompts/agents/assistant.yaml``（PromptLoader 加载）
- checkpointer：``AsyncPostgresSaver`` 单例，thread_id 兼作会话 id；
  checkpoint 表由 ``setup()`` 幂等创建，不进 Alembic
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from collections.abc import Sequence
from typing import Any, cast

import structlog
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware.filesystem import FilesystemPermission
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.agent.core.prompt_loader import get_prompt_loader
from app.agent.runtime.model_factory import build_langchain_model
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.admin.llm_config_service import ResolvedLLMConfig
from app.services.quota.user_llm_service import resolve_llm

logger = structlog.get_logger(__name__)

_pool: AsyncConnectionPool | None = None
# 模型出口指纹 → (agent, last_used)：LRU + 闲置淘汰；MCP 配置变更经 reset 清空
_agents: OrderedDict[str, tuple[CompiledStateGraph, float]] = OrderedDict()
_build_lock = asyncio.Lock()
# 闲置淘汰阈值（秒）
_IDLE_TTL_SECONDS = 2 * 3600.0


def _fingerprint(cfg: ResolvedLLMConfig) -> str:
    """模型出口指纹（含 api_key 哈希，不含明文）。"""
    key_digest = hashlib.sha256(cfg.api_key.encode()).hexdigest()
    raw = "|".join([cfg.protocol, cfg.base_url, cfg.model_name, key_digest])
    return hashlib.sha256(raw.encode()).hexdigest()


def _evict_idle() -> None:
    """淘汰闲置超时条目（在持锁路径调用）。"""
    cutoff = time.monotonic() - _IDLE_TTL_SECONDS
    for key in [k for k, (_, used) in _agents.items() if used < cutoff]:
        _agents.pop(key, None)


async def get_checkpointer() -> BaseCheckpointSaver:
    """Postgres checkpointer 单例（懒建连接池）。

    Raises:
        Exception: 连接池建立失败时向上传播，由调用方决定降级策略。
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    global _pool
    if _pool is None:
        settings = get_settings()
        dsn = str(settings.database_url).replace("+asyncpg", "")
        # saver 的 setup() 用 CREATE INDEX CONCURRENTLY，连接必须 autocommit
        # min_size 显式压小：默认 4 会急切建 4 条连接，公网远程 PG 时显著拖慢冷启动
        pool = AsyncConnectionPool(
            conninfo=dsn,
            open=False,
            min_size=2,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        await pool.open()
        _pool = pool
        logger.info("assistant_checkpointer_pool_opened")
    # saver 每个游标自带 dict_row，pool 默认行类型仅是泛型标注差异
    dict_row_pool = cast("AsyncConnectionPool[AsyncConnection[dict[str, Any]]]", _pool)
    return AsyncPostgresSaver(dict_row_pool)


async def setup_assistant_runtime() -> None:
    """应用 lifespan 启动：建池并幂等创建 checkpoint 表。"""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    checkpointer = await get_checkpointer()
    assert isinstance(checkpointer, AsyncPostgresSaver)
    await checkpointer.setup()
    logger.info("assistant_checkpointer_ready")


async def close_assistant_runtime() -> None:
    """应用 lifespan 关闭：释放连接池与缓存的 agent 实例。"""
    global _pool
    _agents.clear()
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("assistant_checkpointer_pool_closed")


def load_assistant_system_prompt() -> str:
    """加载助手系统提示词（prompts/agents/assistant.yaml）。"""
    config = get_prompt_loader().load("agents", "assistant")
    return config.system_prompt


async def get_assistant_agent(
    tools: Sequence[BaseTool] | None = None,
    cfg: ResolvedLLMConfig | None = None,
) -> CompiledStateGraph:
    """组装并按出口指纹缓存对话助手 deepagents 图。

    Args:
        tools: 注入的数据工具；缺省用 ``app.agent.tools.build_assistant_tools()``。
            注意：仅影响本次构建；命中缓存时忽略（工具集变更须先 reset）。
        cfg: 已解析的模型出口（BYOK 用户传入自有配置）；缺省解析系统默认。

    Returns:
        已绑定 checkpointer 的 CompiledStateGraph；同指纹调用直接返回缓存实例。
    """
    if cfg is None:
        async with AsyncSessionLocal() as session:
            cfg, _outlet = await resolve_llm(session)
    fp = _fingerprint(cfg)

    async with _build_lock:
        _evict_idle()
        cached = _agents.get(fp)
        if cached is not None:
            _agents[fp] = (cached[0], time.monotonic())
            _agents.move_to_end(fp)
            return cached[0]

        agent = await _build_agent(tools, cfg)
        capacity = get_settings().quota_agent_cache_size
        while len(_agents) >= max(capacity, 1):
            _agents.popitem(last=False)
        _agents[fp] = (agent, time.monotonic())
        return agent


async def _build_agent(
    tools: Sequence[BaseTool] | None, cfg: ResolvedLLMConfig
) -> CompiledStateGraph:
    """构建一个助手图实例（仅在缓存 miss 时调用，须持 ``_build_lock``）。"""
    from deepagents import create_deep_agent

    if tools is None:
        from app.agent.tools import build_assistant_tools, build_mcp_tools

        tools = [*build_assistant_tools(), *await build_mcp_tools()]

    from app.agent.runtime.assistant_subagents import build_subagents

    skills_dir = get_settings().skills_dir
    backend: CompositeBackend | None = None
    permissions: list[FilesystemPermission] | None = None
    if skills_dir.exists():
        backend = CompositeBackend(
            default=StateBackend(),
            routes={
                "/skills/": FilesystemBackend(
                    root_dir=str(skills_dir), virtual_mode=True
                ),
            },
        )
        permissions = [
            FilesystemPermission(
                operations=["write"], paths=["/skills/**"], mode="deny"
            )
        ]
    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=list(tools),
        system_prompt=load_assistant_system_prompt(),
        middleware=[TodoListMiddleware()],
        subagents=build_subagents(),
        skills=[str(skills_dir)] if skills_dir.exists() else None,
        backend=backend,
        permissions=permissions,
        checkpointer=await get_checkpointer(),
        name="invest-assistant",
    )
    logger.info(
        "assistant_agent_created",
        provider=cfg.provider,
        model=cfg.model_name,
        n_tools=len(tools),
        skills_dir=str(skills_dir) if skills_dir.exists() else None,
    )
    return agent


def reset_assistant_agent() -> None:
    """清空 agent 缓存（MCP 配置变更或测试隔离时调用）。"""
    _agents.clear()
