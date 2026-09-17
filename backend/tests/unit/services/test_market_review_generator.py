"""大盘复盘生成内核测试（persist 校验、就绪预检、agent 内核替换装配）。"""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.core.prompt_loader import PromptSection
from app.core.constants import INDEX_CODES
from app.services.review import market_review_formatter, market_review_generator

_TRADE_DATE = date(2026, 7, 17)

_SECTIONS = [
    PromptSection(key="overview", title="AI 大盘综述"),
    PromptSection(key="risk_advice", title="风险提示与策略建议"),
]

_CONTENTS = {"overview": "综述", "risk_advice": "风险"}


def _config() -> SimpleNamespace:
    return SimpleNamespace(sections=_SECTIONS)


def _patch_redis_lock(acquired: bool = True):
    @asynccontextmanager
    async def _fake_lock(*args: object, **kwargs: object):
        yield acquired

    return patch.object(market_review_generator, "redis_lock", _fake_lock)


@pytest.mark.unit
class TestLoadBaseReviewHashMode:
    """生成缓存路径须精确匹配契约哈希；用户读路径跨契约版本回退同日最新。"""

    def _row(self) -> SimpleNamespace:
        return SimpleNamespace(
            id=1,
            structured_output={"trade_date": "2026-09-16", "sections": {"overview": "综述"}},
            model="m",
            created_at=datetime(2026, 9, 16, 18, 40, tzinfo=timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_default_requires_hash_match(self) -> None:
        with patch.object(
            market_review_generator.ai_analysis_repository,
            "load_latest_success",
            AsyncMock(return_value=self._row()),
        ) as mock_repo:
            await market_review_generator._load_base_review(
                AsyncMock(), _TRADE_DATE, _SECTIONS
            )

        assert mock_repo.await_args.kwargs["input_hash"] is not None
        assert mock_repo.await_args.kwargs["trade_date"] is None

    @pytest.mark.asyncio
    async def test_read_path_falls_back_across_contract_versions(self) -> None:
        with patch.object(
            market_review_generator.ai_analysis_repository,
            "load_latest_success",
            AsyncMock(return_value=self._row()),
        ) as mock_repo:
            base = await market_review_generator._load_base_review(
                AsyncMock(), _TRADE_DATE, _SECTIONS, require_hash_match=False
            )

        assert mock_repo.await_args.kwargs["input_hash"] is None
        assert mock_repo.await_args.kwargs["trade_date"] == _TRADE_DATE
        assert base is not None
        assert [s.key for s in base.response.sections] == ["overview"]


@pytest.mark.unit
class TestBuildResponseEmptySectionSkip:
    """历史记录按旧契约落库：新增分区键无内容时不渲染空白卡片。"""

    _SECTIONS = [
        PromptSection(key="overview", title="AI 大盘综述"),
        PromptSection(key="news_analysis", title="消息面复盘"),
        PromptSection(key="risk_advice", title="风险提示与策略建议"),
    ]

    def _build(self, contents: dict[str, str]):
        return market_review_formatter.build_response(
            trade_date=_TRADE_DATE,
            contents=contents,
            sections=self._SECTIONS,
            model=None,
            generated_at=datetime.now(timezone.utc),
            cached=True,
            edited=False,
        )

    def test_skips_missing_section_keys(self) -> None:
        response = self._build({"overview": "综述", "risk_advice": "风险"})

        assert [s.key for s in response.sections] == ["overview", "risk_advice"]

    def test_skips_blank_content_sections(self) -> None:
        response = self._build(
            {"overview": "综述", "news_analysis": "   ", "risk_advice": "风险"}
        )

        assert [s.key for s in response.sections] == ["overview", "risk_advice"]

    def test_keeps_non_empty_sections_in_declared_order(self) -> None:
        response = self._build(
            {"overview": "综述", "news_analysis": "消息", "risk_advice": "风险"}
        )

        assert [s.key for s in response.sections] == [
            "overview",
            "news_analysis",
            "risk_advice",
        ]


@pytest.mark.unit
class TestPersistMarketReviewResult:
    @pytest.mark.asyncio
    async def test_raises_when_section_missing_or_blank(self) -> None:
        with patch.object(
            market_review_generator, "load_prompt_config", lambda: _config()
        ):
            for bad in (
                {"overview": "综述"},
                {"overview": "综述", "risk_advice": "   "},
            ):
                with pytest.raises(ValueError, match="risk_advice"):
                    await market_review_generator.persist_market_review_result(
                        AsyncMock(), trade_date=_TRADE_DATE, contents=bad, model="m"
                    )

    @pytest.mark.asyncio
    async def test_persists_filtered_contents_and_builds_response(self) -> None:
        persist_mock = AsyncMock()
        with (
            patch.object(
                market_review_generator, "load_prompt_config", lambda: _config()
            ),
            patch.object(market_review_generator, "_persist", persist_mock),
        ):
            response = await market_review_generator.persist_market_review_result(
                AsyncMock(),
                trade_date=_TRADE_DATE,
                contents={"overview": "综述", "risk_advice": "风险", "junk": "x"},
                model="openai/gpt-4o",
            )

        persist_mock.assert_awaited_once()
        args = persist_mock.await_args.args
        # _persist(session, hash, model, contents, trade_date, latency_ms)
        assert args[2] == "openai/gpt-4o"
        assert args[3] == _CONTENTS
        assert args[4] == _TRADE_DATE
        assert args[5] == 0

        assert response.trade_date == _TRADE_DATE
        assert {item.key: item.content for item in response.sections} == _CONTENTS
        assert response.cached is False
        assert response.edited is False

    @pytest.mark.asyncio
    async def test_threads_latency_ms_into_persist(self) -> None:
        persist_mock = AsyncMock()
        with (
            patch.object(
                market_review_generator, "load_prompt_config", lambda: _config()
            ),
            patch.object(market_review_generator, "_persist", persist_mock),
        ):
            await market_review_generator.persist_market_review_result(
                AsyncMock(),
                trade_date=_TRADE_DATE,
                contents=dict(_CONTENTS),
                model="openai/gpt-4o",
                latency_ms=65000,
            )

        assert persist_mock.await_args.args[5] == 65000


@pytest.mark.unit
class TestGenerateReadiness:
    def _generate_patches(
        self,
        overview: SimpleNamespace,
        quotes: list[SimpleNamespace] | None = None,
    ):
        if quotes is None:
            quotes = [SimpleNamespace(code=code) for code in INDEX_CODES]
        return (
            patch(
                "app.services.market.market_stats_service.get_market_stats",
                AsyncMock(return_value=SimpleNamespace(trade_date=_TRADE_DATE)),
            ),
            patch(
                "app.services.market.trade_calendar_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch.object(
                market_review_generator, "load_prompt_config", lambda: _config()
            ),
            patch(
                "app.services.market.sector_service.get_sector_overview",
                AsyncMock(return_value=overview),
            ),
            patch(
                "app.services.market.index_quotation_service.get_index_quotes",
                AsyncMock(return_value=quotes),
            ),
            _patch_redis_lock(),
        )

    @pytest.mark.asyncio
    async def test_raises_not_ready_when_sector_data_missing(self) -> None:
        empty = SimpleNamespace(top_inflow=[], top_outflow=[], leading=[])
        p = self._generate_patches(empty)
        with (
            p[0],
            p[1],
            p[2],
            p[3],
            p[4],
            p[5],
            pytest.raises(market_review_generator.ReviewInputDataNotReadyError),
        ):
            await market_review_generator.generate_market_review(
                AsyncMock(), _TRADE_DATE, regenerate=True
            )

    @pytest.mark.asyncio
    async def test_leading_without_change_pct_counts_as_not_ready(self) -> None:
        overview = SimpleNamespace(
            top_inflow=[], top_outflow=[], leading=[SimpleNamespace(change_pct=None)]
        )
        p = self._generate_patches(overview)
        with (
            p[0],
            p[1],
            p[2],
            p[3],
            p[4],
            p[5],
            pytest.raises(market_review_generator.ReviewInputDataNotReadyError),
        ):
            await market_review_generator.generate_market_review(
                AsyncMock(), _TRADE_DATE, regenerate=True
            )

    @pytest.mark.asyncio
    async def test_raises_not_ready_when_index_quotes_missing(self) -> None:
        """指数行情缺位（日 K 与快照均无）时预检拦截，避免生成并缓存残缺复盘。"""
        overview = SimpleNamespace(
            top_inflow=[SimpleNamespace(sector_name="半导体")],
            top_outflow=[],
            leading=[],
        )
        # 仅富时A50 命中（期货 T+1 日期惯例），四大 A 股指数缺席
        partial = [SimpleNamespace(code="CN00Y")]
        p = self._generate_patches(overview, quotes=partial)
        with (
            p[0],
            p[1],
            p[2],
            p[3],
            p[4],
            p[5],
            pytest.raises(market_review_generator.ReviewInputDataNotReadyError),
        ):
            await market_review_generator.generate_market_review(
                AsyncMock(), _TRADE_DATE, regenerate=True
            )

    @pytest.mark.asyncio
    async def test_ready_data_runs_skill_and_persists(self) -> None:
        overview = SimpleNamespace(
            top_inflow=[SimpleNamespace(sector_name="半导体")],
            top_outflow=[],
            leading=[],
        )
        persist_mock = AsyncMock()
        p = self._generate_patches(overview)
        with (
            p[0],
            p[1],
            p[2],
            p[3],
            p[4],
            p[5],
            patch.object(market_review_generator, "_persist", persist_mock),
            patch(
                "app.agent.skills.market_review_agent.run_skill",
                AsyncMock(return_value=(dict(_CONTENTS), "openai/gpt-4o", 1234)),
            ),
        ):
            response = await market_review_generator.generate_market_review(
                AsyncMock(), _TRADE_DATE, regenerate=True
            )

        assert response.cached is False
        assert {item.key: item.content for item in response.sections} == _CONTENTS
        assert response.model == "openai/gpt-4o"
        persist_mock.assert_awaited_once()
        assert persist_mock.await_args.args[5] == 1234
