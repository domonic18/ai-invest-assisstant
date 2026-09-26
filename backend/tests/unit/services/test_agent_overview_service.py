"""交易 Agent 总览聚合服务测试（D28：next_tasks 按 plan/review_cadence 门控）。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.kb import KbSource
from app.models.paper_trade import TradingAgent
from app.services.trading import agent_overview_service as svc


def _session(schedules: list[SimpleNamespace]) -> MagicMock:
    session = MagicMock()
    ret = MagicMock()
    ret.all.return_value = schedules
    session.scalars = AsyncMock(return_value=ret)
    return session


def _row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "agent_key": "short-line",
        "plan_cadence": "daily",
        "review_cadence": "daily",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
class TestCadenceDue:
    @pytest.mark.asyncio
    async def test_daily_requires_trading_day_only(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=True),
        ):
            assert (
                await svc._cadence_due(MagicMock(), "daily", datetime(2026, 9, 28).date())
                is True
            )

    @pytest.mark.asyncio
    async def test_non_trading_day_never_due(self) -> None:
        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=False),
        ):
            assert (
                await svc._cadence_due(MagicMock(), "daily", datetime(2026, 9, 26).date())
                is False
            )

    @pytest.mark.asyncio
    async def test_weekly_requires_period_end(self) -> None:
        with (
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.trading.agent_review_service.is_last_trading_day_of_week",
                AsyncMock(return_value=False),
            ),
        ):
            assert (
                await svc._cadence_due(MagicMock(), "weekly", datetime(2026, 9, 28).date())
                is False
            )


@pytest.mark.unit
class TestNextTaskTimes:
    @pytest.mark.asyncio
    async def test_returns_sorted_utc_tasks_for_daily_agent(self) -> None:
        session = _session(
            [
                SimpleNamespace(
                    task_name="agent_daily_plan_1900", schedule="30 19 * * 1-5"
                ),
                SimpleNamespace(
                    task_name="paper_trade_review_1610", schedule="0 19 * * 1-5"
                ),
            ]
        )
        row = _row()
        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=True),
        ):
            tasks = await svc._next_task_times(session, row)
        assert [t.task for t in tasks] == ["模拟盘分层复盘", "每日选股与交易计划"]
        assert all(t.scheduled_at.tzinfo == timezone.utc for t in tasks)

    @pytest.mark.asyncio
    async def test_weekly_agent_waits_for_due_candidate(self) -> None:
        """weekly 门控：非周期日候选被跳过，直到命中 due 候选（下周五 19:30）。"""
        session = _session(
            [SimpleNamespace(task_name="agent_daily_plan_1900", schedule="30 19 * * 1-5")]
        )
        row = _row(plan_cadence="weekly")

        async def _due(_s: object, cadence: str, day: object) -> bool:
            return cadence == "weekly" and day.isoweekday() == 5

        with patch.object(svc, "_cadence_due", _due):
            tasks = await svc._next_task_times(session, row)

        assert len(tasks) == 1
        assert tasks[0].scheduled_at.isoweekday() == 5

    @pytest.mark.asyncio
    async def test_never_due_task_is_omitted(self) -> None:
        session = _session(
            [
                SimpleNamespace(task_name="agent_daily_plan_1900", schedule="30 19 * * 1-5"),
                SimpleNamespace(task_name="paper_trade_review_1610", schedule="0 19 * * 1-5"),
            ]
        )
        row = _row()

        async def _never_due(_s: object, cadence: str, day: object) -> bool:
            return False

        with patch.object(svc, "_cadence_due", _never_due):
            tasks = await svc._next_task_times(session, row)

        assert tasks == []

    @pytest.mark.asyncio
    async def test_inactive_or_blank_schedule_omitted(self) -> None:
        session = _session(
            [SimpleNamespace(task_name="agent_daily_plan_1900", schedule="")]
        )
        tasks = await svc._next_task_times(session, _row())
        assert tasks == []


def _agent_row(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "agent_key": "short-line",
        "name": "短线猎手",
        "tagline": "日内强势股猎手",
        "strategy_desc": "打板/低吸",
        "style_desc": "激进",
        "llm_config_id": None,
        "methodology_source_id": 1,
        "risk_max_position_pct": 20.0,
        "risk_max_total_pct": 80.0,
        "risk_max_daily_orders": 10,
        "auto_exec_enabled": True,
        "status": "active",
        "plan_cadence": "daily",
        "review_cadence": "daily",
        "sort_order": 1,
        "prompt_id": "trading_agent_short_line",
        "accent_color": "#3b82f6",
        "updated_at": datetime(2026, 9, 25, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _collector_task(task_name: str, is_active: bool = True) -> SimpleNamespace:
    schedules = {
        "agent_daily_plan_1900": "30 19 * * 1-5",
        "paper_trade_review_1610": "0 19 * * 1-5",
        "paper_trade_sync_1600": "0 16 * * 1-5",
    }
    return SimpleNamespace(
        task_name=task_name, schedule=schedules[task_name], is_active=is_active
    )


@pytest.mark.unit
class TestAutomationTasks:
    @pytest.mark.asyncio
    async def test_three_tasks_with_cron_next_and_last(self) -> None:
        session = MagicMock()
        ret = MagicMock()
        ret.all.return_value = [
            _collector_task("agent_daily_plan_1900"),
            _collector_task("paper_trade_review_1610", is_active=False),
            _collector_task("paper_trade_sync_1600"),
        ]
        session.scalars = AsyncMock(return_value=ret)
        last_log = SimpleNamespace(
            started_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
            finished_at=None,
            status="success",
        )
        session.scalar = AsyncMock(return_value=last_log)

        with patch(
            "app.services.market.trade_calendar_service.is_trading_day",
            AsyncMock(return_value=True),
        ):
            items = await svc._automation_tasks(session, _agent_row())

        assert [i.key for i in items] == [
            "agent_daily_plan_1900",
            "paper_trade_review_1610",
            "paper_trade_sync_1600",
        ]
        plan_task = items[0]
        assert plan_task.label == "每日选股与交易计划（19:30）"
        assert plan_task.task_active is True
        assert plan_task.cadence == "daily"
        assert plan_task.cron == "30 19 * * 1-5"
        assert plan_task.next_run_at is not None
        assert plan_task.next_run_at.tzinfo == timezone.utc
        assert plan_task.last_status == "success"
        assert plan_task.last_run_at == datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)
        # 停用任务不计算下次触发
        assert items[1].task_active is False
        assert items[1].next_run_at is None
        # sync 为全局任务，无 cadence
        assert items[2].cadence is None

    @pytest.mark.asyncio
    async def test_missing_task_row_renders_inactive_placeholder(self) -> None:
        session = MagicMock()
        ret = MagicMock()
        ret.all.return_value = []
        session.scalars = AsyncMock(return_value=ret)
        session.scalar = AsyncMock(return_value=None)
        items = await svc._automation_tasks(session, _agent_row())
        assert len(items) == 3
        assert all(i.task_active is False and i.next_run_at is None for i in items)
        assert all(i.last_status is None for i in items)


@pytest.mark.unit
class TestGetAgentStatus:
    @pytest.mark.asyncio
    async def test_capability_view_assembles_all_sections(self) -> None:
        session = MagicMock()

        async def _get(_type, key):
            if _type is TradingAgent:
                return _agent_row(llm_config_id=None)
            if _type is KbSource:
                return SimpleNamespace(id=1, name="趋势交易理论", enabled=True)
            return None

        session.get = AsyncMock(side_effect=_get)
        counts_ret = MagicMock()
        counts_ret.all.return_value = [("discipline", 2), ("method", 1), ("lesson", 3)]
        session.execute = AsyncMock(return_value=counts_ret)
        tasks_ret = MagicMock()
        tasks_ret.all.return_value = [_collector_task("agent_daily_plan_1900")]
        session.scalars = AsyncMock(return_value=tasks_ret)
        session.scalar = AsyncMock(return_value=None)
        activity = svc.AgentActivityItem(
            kind="plan", title="600000 buy 计划", occurred_at=None
        )

        with (
            patch(
                "app.services.trading.agent_overview_service.plan_skill_id",
                MagicMock(return_value="trading-short-line"),
            ),
            patch(
                "app.services.trading.agent_overview_service.get_skill",
                MagicMock(return_value=SimpleNamespace(label="短线猎手作业程序")),
            ),
            patch.object(svc, "_plan_activity", AsyncMock(return_value=[activity])),
            patch.object(svc, "_review_activity", AsyncMock(return_value=[])),
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
        ):
            view = await svc.get_agent_status(session, "short-line")

        assert view.profile.agent_key == "short-line"
        assert view.llm_name is None
        assert view.methodology_source_name == "趋势交易理论"
        assert view.skill_id == "trading-short-line"
        assert view.skill_label == "短线猎手作业程序"
        assert view.skill_is_shared_default is False
        assert view.memory_counts.discipline == 2
        assert view.memory_counts.method == 1
        assert view.memory_counts.lesson == 3
        assert view.memory_counts.active_total == 6
        assert len(view.automation) == 3
        assert view.recent_activity == [activity]

    @pytest.mark.asyncio
    async def test_shared_default_skill_falls_back_label_to_id(self) -> None:
        session = MagicMock()

        async def _get(_type, key):
            if _type is TradingAgent:
                return _agent_row(methodology_source_id=None)
            return None

        session.get = AsyncMock(side_effect=_get)
        counts_ret = MagicMock()
        counts_ret.all.return_value = []
        session.execute = AsyncMock(return_value=counts_ret)
        tasks_ret = MagicMock()
        tasks_ret.all.return_value = []
        session.scalars = AsyncMock(return_value=tasks_ret)
        session.scalar = AsyncMock(return_value=None)

        with (
            patch(
                "app.services.trading.agent_overview_service.plan_skill_id",
                MagicMock(return_value="trading-default"),
            ),
            patch(
                "app.services.trading.agent_overview_service.get_skill",
                MagicMock(return_value=None),
            ),
            patch.object(svc, "_plan_activity", AsyncMock(return_value=[])),
            patch.object(svc, "_review_activity", AsyncMock(return_value=[])),
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
        ):
            view = await svc.get_agent_status(session, "short-line")

        assert view.skill_id == "trading-default"
        assert view.skill_is_shared_default is True
        assert view.skill_label == "trading-default"
        assert view.methodology_source_name is None
        assert view.memory_counts.active_total == 0


@pytest.mark.unit
class TestPlanActivityStructured:
    """D30：活动条目结构化（title 买入/卖出计划 + stock_code + 名称回填）。"""

    @pytest.mark.asyncio
    async def test_plan_rows_render_semantic_title_with_code(self) -> None:
        session = _session(
            [
                SimpleNamespace(
                    stock_code="600000",
                    plan_type="buy",
                    status="active",
                    triggered_at=None,
                    created_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
                ),
                SimpleNamespace(
                    stock_code="000001",
                    plan_type="sell",
                    status="triggered",
                    triggered_at=datetime(2026, 9, 25, 1, 0, tzinfo=timezone.utc),
                    created_at=datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        items = await svc._plan_activity(session, "short-line")
        assert [i.title for i in items] == ["买入计划", "卖出计划"]
        assert [i.stock_code for i in items] == ["600000", "000001"]
        assert items[1].detail == "已触发下单"
        assert items[1].occurred_at == datetime(2026, 9, 25, 1, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_fill_stock_names_batches_missing_codes_only(self) -> None:
        session = MagicMock()
        repo_ret = {"600000": "浦发银行"}
        with patch(
            "app.services.trading.agent_overview_service.StockRepository"
        ) as repo_cls:
            repo_cls.return_value.get_names_by_codes = AsyncMock(return_value=repo_ret)
            items = await svc._fill_stock_names(
                session,
                [
                    svc.AgentActivityItem(
                        kind="plan", title="买入计划", stock_code="600000"
                    ),
                    svc.AgentActivityItem(kind="plan", title="卖出计划"),
                ],
            )
        assert items[0].stock_name == "浦发银行"
        assert items[1].stock_name is None
        repo_cls.return_value.get_names_by_codes.assert_awaited_once_with(["600000"])

    @pytest.mark.asyncio
    async def test_fill_stock_names_skips_query_when_no_codes(self) -> None:
        session = MagicMock()
        with patch(
            "app.services.trading.agent_overview_service.StockRepository"
        ) as repo_cls:
            items = await svc._fill_stock_names(
                session, [svc.AgentActivityItem(kind="review", title="day 复盘已生成")]
            )
        assert items[0].stock_name is None
        repo_cls.assert_not_called()


@pytest.mark.unit
class TestGetAgentSkillFiles:
    """D30：作业技能包可视化（镜像目录直读 + 方法论挂载）。"""

    @pytest.mark.asyncio
    async def test_reads_skill_dir_files_and_null_methodology(
        self, tmp_path
    ) -> None:
        skill_dir = tmp_path / "trading-short-line"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# 短线作业程序", encoding="utf-8")
        (skill_dir / "prompt.yaml").write_text("id: trading-short-line\n", encoding="utf-8")
        (skill_dir / "junk.pyc").write_bytes(b"\x00")
        settings = SimpleNamespace(
            skills_dir=tmp_path, skill_files_max_count=20, skill_file_max_bytes=100_000
        )

        session = MagicMock()
        session.get = AsyncMock(return_value=_agent_row(methodology_source_id=None))
        with (
            patch(
                "app.services.trading.agent_overview_service.get_settings",
                MagicMock(return_value=settings),
            ),
            patch(
                "app.services.trading.agent_overview_service.plan_skill_id",
                MagicMock(return_value="trading-short-line"),
            ),
            patch(
                "app.services.trading.agent_overview_service.get_skill",
                MagicMock(return_value=SimpleNamespace(label="短线猎手作业程序")),
            ),
            patch(
                "app.services.trading.agent_overview_service.build_methodology_view",
                AsyncMock(return_value=None),
            ),
        ):
            view = await svc.get_agent_skill_files(session, "short-line")

        assert view.skill_id == "trading-short-line"
        assert view.skill_label == "短线猎手作业程序"
        assert view.skill_is_shared_default is False
        assert [f.path for f in view.files] == ["SKILL.md", "prompt.yaml"]
        assert view.files[0].content == "# 短线作业程序"
        assert view.methodology is None

    @pytest.mark.asyncio
    async def test_missing_dir_falls_back_empty_files_with_methodology(
        self, tmp_path
    ) -> None:
        settings = SimpleNamespace(
            skills_dir=tmp_path, skill_files_max_count=20, skill_file_max_bytes=100_000
        )
        session = MagicMock()
        session.get = AsyncMock(return_value=_agent_row(methodology_source_id=1))
        methodology = {
            "source_id": 1,
            "source_name": "趋势交易理论",
            "outline": "- 第一章 体系",
            "disciplines": [{"id": 1, "title": "不追高", "body": "偏离 3% 不追"}],
            "points": [{"point_type": "method", "title": "回踩接回", "body": "…"}],
        }
        with (
            patch(
                "app.services.trading.agent_overview_service.get_settings",
                MagicMock(return_value=settings),
            ),
            patch(
                "app.services.trading.agent_overview_service.plan_skill_id",
                MagicMock(return_value="trading-default"),
            ),
            patch(
                "app.services.trading.agent_overview_service.get_skill",
                MagicMock(return_value=None),
            ),
            patch(
                "app.services.trading.agent_overview_service.build_methodology_view",
                AsyncMock(return_value=methodology),
            ),
        ):
            view = await svc.get_agent_skill_files(session, "short-line")

        assert view.skill_id == "trading-default"
        assert view.skill_label == "trading-default"
        assert view.skill_is_shared_default is True
        assert view.files == []
        assert view.methodology is not None
        assert view.methodology.source_name == "趋势交易理论"
        assert view.methodology.disciplines[0].title == "不追高"
        assert view.methodology.points[0].point_type == "method"
