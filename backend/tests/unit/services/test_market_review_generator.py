"""大盘复盘生成内核测试（persist 校验、就绪预检、agent 内核替换装配）。"""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.core.prompt_loader import PromptSection
from app.services.review import market_review_generator

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
    def _generate_patches(self, overview: SimpleNamespace):
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
