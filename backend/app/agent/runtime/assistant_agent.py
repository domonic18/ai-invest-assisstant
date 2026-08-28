"""对话助手 deepagents 运行时组装（单例懒加载）。

- 模型：复用 ``llm_config`` 默认配置（``resolve_default_llm``）
- 系统提示词：``prompts/agents/assistant.yaml``（PromptLoader 加载）
- checkpointer：``AsyncPostgresSaver`` 单例，thread_id 兼作会话 id；
  checkpoint 表由 ``setup()`` 幂等创建，不进 Alembic
"""

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

from app.agent.core.prompt_loader import PromptLoader
from app.agent.runtime.model_factory import build_langchain_model
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.llm_config_service import resolve_default_llm

logger = structlog.get_logger(__name__)

_pool: AsyncConnectionPool | None = None
_agent: CompiledStateGraph | None = None


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
        pool = AsyncConnectionPool(
            conninfo=dsn,
            open=False,
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
    global _pool, _agent
    _agent = None
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("assistant_checkpointer_pool_closed")


def load_assistant_system_prompt() -> str:
    """加载助手系统提示词（prompts/agents/assistant.yaml）。"""
    config = PromptLoader(get_settings().prompts_dir).load("agents", "assistant")
    return config.system_prompt


async def get_assistant_agent(
    tools: Sequence[BaseTool] | None = None,
) -> CompiledStateGraph:
    """组装并缓存对话助手 deepagents 图。

    Args:
        tools: 注入的数据工具；缺省用 ``assistant_tools.build_assistant_tools()``。

    Returns:
        已绑定 checkpointer 的 CompiledStateGraph；后续调用直接返回缓存实例。
    """
    global _agent
    if _agent is not None:
        return _agent

    from deepagents import create_deep_agent

    if tools is None:
        from app.agent.tools import build_assistant_tools

        tools = build_assistant_tools()

    from app.agent.runtime.assistant_subagents import build_subagents

    async with AsyncSessionLocal() as session:
        cfg = await resolve_default_llm(session)

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
    _agent = create_deep_agent(
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
    return _agent


def reset_assistant_agent() -> None:
    """丢弃缓存的 agent 实例（后台 LLM 配置变更或测试隔离时调用）。"""
    global _agent
    _agent = None
