"""交易 Agent 执行会话 recorder（会话管理 D35）。

agent_run / agent_run_step 的唯一写入方：服务层在生成入口构造 recorder，
按步骤 ``step()`` 记录执行轨迹，``finish()`` 收口状态与结果摘要。

观测与业务解耦的两条硬约束：
- **独立 session**：每次写入新开 ``AsyncSessionLocal`` 即写即 commit，
  业务事务回滚不连带丢观测行（failed run 也要留轨迹）；
- **观测永不拖垮业务**：recorder 内部异常一律吞掉 + structlog warning，
  调用方无需 try/except 包裹。

payload 截断策略：单段（str/list/dict 值）超 8KB 截断加标记；prompt 与
结构化输出全文等大文本段（key 在 ``_LARGE_PAYLOAD_KEYS``）上限放大到 64KB。
"""

import json
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import update

from app.core.clock import utc_now
from app.core.database import AsyncSessionLocal
from app.models.agent_run import AgentRun, AgentRunStep

logger = structlog.get_logger(__name__)

_PAYLOAD_SEGMENT_LIMIT = 8 * 1024
_PAYLOAD_LARGE_LIMIT = 64 * 1024
_LARGE_PAYLOAD_KEYS = frozenset({"prompt", "output"})

_STEP_SUCCESS = "success"
_STEP_FAILED = "failed"


def _marker(original_bytes: int, limit: int) -> str:
    return f"\n…[截断：原始 {original_bytes} 字节，存储上限 {limit}B]"


def _truncate_segment(key: str, value: Any, limit: int) -> Any:
    """单段截断：str 按字节裁剪，list/dict 超限整体序列化后裁剪（保留标记）。"""
    if isinstance(value, str):
        raw = value.encode("utf-8")
        if len(raw) <= limit:
            return value
        cut = raw[:limit].decode("utf-8", errors="ignore")
        return f"{cut}{_marker(len(raw), limit)}"
    if isinstance(value, (list, dict)):
        raw = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        if len(raw) <= limit:
            return value
        cut = raw[:limit].decode("utf-8", errors="ignore")
        return f"{cut}{_marker(len(raw), limit)}"
    return value


def _truncate_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """按段截断 payload；prompt/结构化输出全文段使用放大后的上限。"""
    if payload is None:
        return None
    return {
        key: _truncate_segment(
            key,
            value,
            _PAYLOAD_LARGE_LIMIT if key in _LARGE_PAYLOAD_KEYS else _PAYLOAD_SEGMENT_LIMIT,
        )
        for key, value in payload.items()
    }


def _json_safe(value: Any) -> Any:
    """summary 兜底序列化（date 等非 JSON 原生类型转字符串），失败返回 None。"""
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return None


class AgentRunRecorder:
    """交易 Agent 自动化任务执行会话记录器。

    生命周期：``start()`` 落 running 会话头 → ``step()`` 逐段记录执行步骤 →
    ``finish()`` 收口（success/failed/skipped + summary）。异常路径调用方
    仍需 ``finish("failed", error_msg=...)`` 后原样上抛。
    """

    def __init__(
        self,
        *,
        agent_key: str,
        kind: str,
        period: str | None = None,
        trigger: str = "scheduled",
        trade_date: date | None = None,
        collector_log_id: int | None = None,
    ) -> None:
        self.agent_key = agent_key
        self.kind = kind
        self.period = period
        self.trigger = trigger
        self.trade_date = trade_date
        self.collector_log_id = collector_log_id
        self._run_id: int | None = None
        self._seq = 0
        self._started_at = utc_now()

    @property
    def run_id(self) -> int | None:
        """会话行 id（start 失败时为 None，后续写入自动跳过）。"""
        return self._run_id

    async def start(self) -> None:
        """落 running 会话头；失败仅告警，业务流程照常执行。"""
        try:
            async with AsyncSessionLocal() as session:
                row = AgentRun(
                    agent_key=self.agent_key,
                    kind=self.kind,
                    period=self.period,
                    trigger_type=self.trigger,
                    trade_date=self.trade_date,
                    status="running",
                    started_at=self._started_at,
                    collector_log_id=self.collector_log_id,
                )
                session.add(row)
                await session.commit()
                self._run_id = row.id
        except Exception:
            logger.warning(
                "agent_run.start_failed",
                agent_key=self.agent_key,
                kind=self.kind,
                exc_info=True,
            )

    @asynccontextmanager
    async def step(
        self,
        key: str,
        title: str,
        payload_builder: Callable[[], dict[str, Any] | None] | None = None,
    ) -> AsyncIterator[None]:
        """计时并落一条执行步骤；body 抛错记 failed 后原样上抛。

        payload_builder 在 body 结束（含失败）后调用：正常路径可同时捕获
        输入与输出；失败路径引用未定义变量而抛错时吞掉（payload 落 None）。
        """
        self._seq += 1
        seq = self._seq
        started_at = utc_now()
        t0 = time.monotonic()
        status = _STEP_SUCCESS
        try:
            yield
        except BaseException:
            status = _STEP_FAILED
            raise
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            payload: dict[str, Any] | None = None
            if payload_builder is not None:
                try:
                    payload = _truncate_payload(payload_builder())
                except Exception:
                    logger.warning("agent_run.step_payload_failed", step=key, exc_info=True)
            await self._write_step(seq, key, title, status, started_at, duration_ms, payload)

    async def finish(
        self,
        status: str = "success",
        summary: dict[str, Any] | None = None,
        error_msg: str | None = None,
    ) -> None:
        """收口会话头：状态 + 结果摘要 + 总耗时（自构造 recorder 起计）。"""
        if self._run_id is None:
            return
        finished_at = utc_now()
        duration_ms = int(
            (finished_at - self._started_at) / timedelta(milliseconds=1)
        )
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(AgentRun)
                    .where(AgentRun.id == self._run_id)
                    .values(
                        status=status,
                        finished_at=finished_at,
                        duration_ms=duration_ms,
                        error_msg=error_msg,
                        summary=_json_safe(summary),
                    )
                )
                await session.commit()
        except Exception:
            logger.warning(
                "agent_run.finish_failed",
                run_id=self._run_id,
                status=status,
                exc_info=True,
            )

    async def _write_step(
        self,
        seq: int,
        key: str,
        title: str,
        status: str,
        started_at: datetime,
        duration_ms: int,
        payload: dict[str, Any] | None,
    ) -> None:
        if self._run_id is None:
            return
        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    AgentRunStep(
                        run_id=self._run_id,
                        seq=seq,
                        step_key=key,
                        title=title,
                        status=status,
                        started_at=started_at,
                        duration_ms=duration_ms,
                        payload=payload,
                    )
                )
                await session.commit()
        except Exception:
            logger.warning(
                "agent_run.step_write_failed",
                run_id=self._run_id,
                step=key,
                exc_info=True,
            )
