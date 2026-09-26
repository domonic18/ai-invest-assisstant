"""交易 Agent deepagents 运行时（每 Agent 一实例，多 Agent 基座 D24）。

与人工助手平行的独立会话体（D16：系统级，非多租户）：
- 模型：``trading_agent.llm_config_id`` 指定出口（空 = 平台默认 chat），
  每次构建时现读注册行，改选即时生效；缓存键 = agent_key × 出口指纹 × 工具集版本
- 工具：专属交易工具集（账户/下单/撤单），按 agent_key 闭包绑定，与人工
  助手工具完全隔离（D18）
- 系统提示词：``prompts/agents/<prompt_id>.yaml``（注册行 prompt_id 指定，
  只承载硬纪律与工作流骨架）+ 注册表人设身份段运行时注入（D28：name/
  tagline/style_desc/strategy_desc 编辑即时生效，人设摘要入缓存指纹自动重建）
  + 方法论基座静态层（D30：KB 总纲 + 纪律全量，绑定知识源后注入会话）
- checkpointer：与助手共享 ``AsyncPostgresSaver`` 单例（thread_id 兼作会话 id）

无 subagents / skills / MCP 挂载——交易 Agent 是窄域执行体，不读技能文件。
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from collections.abc import Sequence

import structlog
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import get_prompt_loader
from app.agent.runtime.assistant_agent import _IDLE_TTL_SECONDS, get_checkpointer
from app.agent.runtime.model_factory import build_langchain_model
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.admin.llm_config_service import (
    ResolvedLLMConfig,
    resolve_default_llm,
    resolve_llm_by_id,
)

logger = structlog.get_logger(__name__)

# agent_key × 出口指纹 × 工具集版本 → (agent, last_used)：LRU + 闲置淘汰
_agents: OrderedDict[str, tuple[CompiledStateGraph, float]] = OrderedDict()
_build_lock = asyncio.Lock()


def load_trading_system_prompt(prompt_id: str) -> str:
    """加载交易 Agent 系统提示词（prompts/agents/<prompt_id>.yaml，硬纪律+工作流骨架）。"""
    config = get_prompt_loader().load("agents", prompt_id)
    return config.system_prompt


def _persona_section(
    name: str, tagline: str, style_desc: str, strategy_desc: str
) -> str:
    """注册表人设 → 系统提示词头部身份段（YAML 只留硬纪律+工作流骨架）。

    tagline/style/strategy 可为空（D30 新建精简），空值行不输出。
    """
    identity = f"- 你是 **{name}**"
    if tagline:
        identity += f"（{tagline}）"
    lines = ["## 你的身份（注册表维护，编辑后即时生效）", identity + "。"]
    if style_desc or strategy_desc:
        lines.append(f"- 策略风格：{style_desc}——{strategy_desc}")
    return "\n".join(lines)


async def _methodology_section(
    session: AsyncSession, source_id: int | None
) -> tuple[int | None, str]:
    """方法论基座静态层文本段（总纲 + 纪律全量，D30）。

    会话与计划注入同源（``build_methodology_input``），query_text 传 None
    跳过当日盘面检索层；未绑定/源不可用返回 ``(None, "")`` 不注入。
    """
    if source_id is None:
        return None, ""
    from app.services.trading.agent_methodology import build_methodology_input

    data = await build_methodology_input(session, source_id=source_id, query_text=None)
    if data is None:
        return None, ""
    lines = ["## 方法论基座（KB 知识源静态层，选股与交易的体系依据）"]
    if data["outline"]:
        lines += ["### 体系总纲", str(data["outline"])]
    disciplines = data["disciplines"]
    if disciplines:
        lines.append("### 硬纪律（必须遵守）")
        lines += [f"- {item['title']}：{item['body']}" for item in disciplines]
    return int(source_id), "\n".join(lines)


async def resolve_trading_llm(
    llm_config_id: int | None,
) -> ResolvedLLMConfig:
    """解析交易 Agent 的模型出口：注册行绑定优先，空则平台默认 chat 模型。"""
    async with AsyncSessionLocal() as session:
        if llm_config_id is not None:
            return await resolve_llm_by_id(session, llm_config_id)
        return await resolve_default_llm(session)


def _fingerprint(
    agent_key: str,
    prompt_id: str,
    persona: tuple[str, str, str, str],
    cfg: ResolvedLLMConfig,
    methodology_source_id: int | None = None,
) -> str:
    """agent_key × prompt_id × 人设摘要 × 出口指纹 × 方法论源 × 工具集版本
    （api_key 只入哈希；人设/出口/方法论绑定变更即失效重建，换工具集须 bump
    版本号；方法论内容更新靠闲置淘汰自然刷新）。"""
    from app.agent.tools.trading import TOOLS_VERSION

    key_digest = hashlib.sha256(cfg.api_key.encode()).hexdigest()
    persona_digest = hashlib.sha256("|".join(persona).encode()).hexdigest()
    raw = "|".join(
        [agent_key, prompt_id, persona_digest, cfg.protocol, cfg.base_url, cfg.model_name, key_digest, str(TOOLS_VERSION), str(methodology_source_id)]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _evict_idle() -> None:
    """淘汰闲置超时条目（在持锁路径调用）。"""
    cutoff = time.monotonic() - _IDLE_TTL_SECONDS
    for key in [k for k, (_, used) in _agents.items() if used < cutoff]:
        _agents.pop(key, None)


async def get_trading_agent(
    agent_key: str,
    tools: Sequence[BaseTool] | None = None,
    cfg: ResolvedLLMConfig | None = None,
) -> CompiledStateGraph:
    """组装并缓存指定 Agent 的 deepagents 图（每 Agent 一实例）。

    Args:
        agent_key: 注册表自然键（trading_agent.agent_key）。
        tools: 注入工具集；缺省 ``build_trading_tools(agent_key)``。
            命中缓存时忽略（显式传工具集须先 reset）。
        cfg: 已解析模型出口；缺省按注册行 llm_config_id 解析。

    Returns:
        已绑定共享 checkpointer 的 CompiledStateGraph。
    """
    from app.services.trading.agent_registry import get_agent

    async with AsyncSessionLocal() as session:
        row = await get_agent(session, agent_key)
        prompt_id = row.prompt_id
        llm_config_id = row.llm_config_id
        persona = (row.name, row.tagline, row.style_desc, row.strategy_desc)
        methodology_source_id, methodology_text = await _methodology_section(
            session, row.methodology_source_id
        )

    if cfg is None:
        cfg = await resolve_trading_llm(llm_config_id)
    fp = _fingerprint(agent_key, prompt_id, persona, cfg, methodology_source_id)

    async with _build_lock:
        _evict_idle()
        cached = _agents.get(fp)
        if cached is not None:
            _agents[fp] = (cached[0], time.monotonic())
            _agents.move_to_end(fp)
            return cached[0]

        agent = await _build_agent(
            agent_key, prompt_id, persona, methodology_text, tools, cfg
        )
        capacity = max(get_settings().quota_agent_cache_size, 1)
        while len(_agents) >= capacity:
            _agents.popitem(last=False)
        _agents[fp] = (agent, time.monotonic())
        return agent


async def _build_agent(
    agent_key: str,
    prompt_id: str,
    persona: tuple[str, str, str, str],
    methodology_text: str,
    tools: Sequence[BaseTool] | None,
    cfg: ResolvedLLMConfig,
) -> CompiledStateGraph:
    """构建一个交易 Agent 图实例（仅缓存 miss 时调用，须持 ``_build_lock``）。"""
    from deepagents import create_deep_agent
    from langchain.agents.middleware import TodoListMiddleware

    if tools is None:
        from app.agent.tools.trading import build_trading_tools

        tools = build_trading_tools(agent_key)

    sections = [
        _persona_section(*persona),
        load_trading_system_prompt(prompt_id),
        methodology_text,
    ]
    system_prompt = "\n\n".join(section for section in sections if section)
    agent = create_deep_agent(
        model=build_langchain_model(cfg),
        tools=list(tools),
        system_prompt=system_prompt,
        middleware=[TodoListMiddleware()],
        checkpointer=await get_checkpointer(),
        name=f"trading-agent-{agent_key}",
    )
    logger.info(
        "trading_agent_created",
        agent_key=agent_key,
        prompt_id=prompt_id,
        provider=cfg.provider,
        model=cfg.model_name,
        n_tools=len(tools),
    )
    return agent


def reset_trading_agent() -> None:
    """清空交易 Agent 缓存（配置/工具变更或测试隔离时调用）。"""
    _agents.clear()
