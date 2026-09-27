"""AgentRunRecorder 契约测试（D35 会话管理）。

覆盖三条硬约束：独立 session 即写即 commit、观测异常全吞（业务无感）、
payload 单段 8KB / prompt+output 64KB 截断。session 以 FakeSession 替身
（patch AsyncSessionLocal），不触真实数据库。
"""

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest

from app.models.agent_run import AgentRun, AgentRunStep
from app.services.trading.agent_run_recorder import AgentRunRecorder

_SESSION_TARGET = "app.services.trading.agent_run_recorder.AsyncSessionLocal"


class FakeSession:
    """AsyncSessionLocal() 替身：捕获 add 的行与 execute 的语句。"""

    def __init__(
        self, rows: list[Any], statements: list[Any], *, fail_execute: bool = False
    ) -> None:
        self._rows = rows
        self._statements = statements
        self._fail_execute = fail_execute

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def add(self, row: Any) -> None:
        self._rows.append(row)
        # 模拟 BIGSERIAL 主键回填（recorder.start 依赖 row.id 捕获 run_id）
        if isinstance(row, AgentRun) and row.id is None:
            row.id = 42

    async def commit(self) -> None:
        return None

    async def execute(self, stmt: Any) -> None:
        if self._fail_execute:
            raise RuntimeError("db down")
        self._statements.append(stmt)


class _SessionFactory:
    """可调用工厂替身：多次 ``AsyncSessionLocal()`` 共享同一捕获容器。"""

    def __init__(self) -> None:
        self.rows: list[Any] = []
        self.statements: list[Any] = []
        self.fail_execute = False

    def __call__(self) -> FakeSession:
        return FakeSession(self.rows, self.statements, fail_execute=self.fail_execute)


@pytest.mark.unit
class TestAgentRunRecorder:
    @pytest.mark.asyncio
    async def test_start_persists_running_row_and_backfills_run_id(self) -> None:
        factory = _SessionFactory()
        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(
                agent_key="short-line",
                kind="plan",
                period="day",
                trigger="manual",
                trade_date=date(2026, 9, 25),
                collector_log_id=7,
            )
            await rec.start()

        assert rec.run_id == 42
        row = factory.rows[0]
        assert isinstance(row, AgentRun)
        assert row.status == "running"
        assert row.agent_key == "short-line"
        assert row.kind == "plan"
        assert row.period == "day"
        assert row.trigger_type == "manual"
        assert row.trade_date == date(2026, 9, 25)
        assert row.collector_log_id == 7
        assert row.started_at is not None

    @pytest.mark.asyncio
    async def test_start_failure_degrades_to_noop(self) -> None:
        """start 失败（单测无库/库不可达）：run_id 停留 None，后续写入静默跳过。"""

        def _boom() -> FakeSession:
            raise RuntimeError("db unreachable")

        with patch(_SESSION_TARGET, _boom):
            rec = AgentRunRecorder(agent_key="short-line", kind="plan")
            await rec.start()
            assert rec.run_id is None
            async with rec.step("llm", "LLM 结构化生成"):
                pass
            await rec.finish("success", summary={"cache_hit": False})

    @pytest.mark.asyncio
    async def test_step_records_success_with_payload_and_seq(self) -> None:
        factory = _SessionFactory()
        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(agent_key="short-line", kind="plan")
            await rec.start()
            async with rec.step(
                "llm", "LLM 结构化生成", payload_builder=lambda: {"prompt": "p"}
            ):
                pass

        head, step_row = factory.rows
        assert head.id == 42
        assert isinstance(step_row, AgentRunStep)
        assert step_row.run_id == 42
        assert step_row.seq == 1
        assert step_row.step_key == "llm"
        assert step_row.title == "LLM 结构化生成"
        assert step_row.status == "success"
        assert step_row.payload == {"prompt": "p"}
        assert step_row.duration_ms >= 0
        assert step_row.started_at is not None

    @pytest.mark.asyncio
    async def test_step_body_error_marks_failed_and_reraises(self) -> None:
        factory = _SessionFactory()
        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(agent_key="short-line", kind="plan")
            await rec.start()
            with pytest.raises(ValueError, match="boom"):
                async with rec.step("validate", "后置校验"):
                    raise ValueError("boom")

        step_row = factory.rows[-1]
        assert step_row.status == "failed"
        assert step_row.seq == 1

    @pytest.mark.asyncio
    async def test_step_payload_builder_error_lands_null_payload(self) -> None:
        """失败路径 payload_builder 引用未定义变量：吞掉后 payload 落 None，step 照常落库。"""
        factory = _SessionFactory()

        def _boom() -> dict[str, Any]:
            raise KeyError("undefined_local")

        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(agent_key="short-line", kind="plan")
            await rec.start()
            async with rec.step("llm", "LLM 结构化生成", payload_builder=_boom):
                pass

        step_row = factory.rows[-1]
        assert step_row.status == "success"
        assert step_row.payload is None

    @pytest.mark.asyncio
    async def test_truncates_segments_at_8kb_and_prompt_at_64kb(self) -> None:
        """普通段 8KB 上限；prompt/output 大文本段放大到 64KB（均带截断标记）。"""
        factory = _SessionFactory()
        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(agent_key="short-line", kind="plan")
            await rec.start()
            big_note = "x" * 20000
            async with rec.step(
                "input.context", "上下文合并", payload_builder=lambda: {"note": big_note}
            ):
                pass
            big_prompt = "y" * 70000
            async with rec.step(
                "llm", "LLM 结构化生成", payload_builder=lambda: {"prompt": big_prompt}
            ):
                pass

        note_stored = factory.rows[1].payload["note"]
        assert "…[截断：原始 20000 字节，存储上限 8192B]" in note_stored
        assert note_stored.startswith("x" * 100)
        prompt_stored = factory.rows[2].payload["prompt"]
        assert "…[截断：原始 70000 字节，存储上限 65536B]" in prompt_stored
        assert len(prompt_stored.encode("utf-8")) < 70000

    @pytest.mark.asyncio
    async def test_finish_writes_status_summary_and_duration(self) -> None:
        factory = _SessionFactory()
        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(agent_key="short-line", kind="review", period="day")
            await rec.start()
            await rec.finish(
                "skipped", summary={"cache_hit": True, "day": date(2026, 9, 25)}
            )

        assert len(factory.rows) == 1  # finish 走 UPDATE，不再 add
        params = factory.statements[0].compile().params
        assert params["status"] == "skipped"
        assert params["error_msg"] is None
        assert isinstance(params["duration_ms"], int)
        # summary 经 _json_safe：date 转字符串（JSONB 可序列化）
        assert params["summary"] == {"cache_hit": True, "day": "2026-09-25"}

    @pytest.mark.asyncio
    async def test_finish_without_start_is_noop(self) -> None:
        factory = _SessionFactory()
        rec = AgentRunRecorder(agent_key="short-line", kind="plan")
        await rec.finish("failed", error_msg="x")
        assert factory.rows == []
        assert factory.statements == []

    @pytest.mark.asyncio
    async def test_finish_failure_is_swallowed(self) -> None:
        """收口写库失败只告警：观测永不拖垮业务。"""
        factory = _SessionFactory()
        factory.fail_execute = True
        with patch(_SESSION_TARGET, factory):
            rec = AgentRunRecorder(agent_key="short-line", kind="plan")
            await rec.start()
            await rec.finish("success", summary={})
