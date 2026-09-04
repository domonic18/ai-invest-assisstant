"""个股每日 AI 分析服务契约测试（缓存键、缓存命中、降级取数与软校验）。"""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.core.prompt_loader import PromptSection
from app.services.review import stock_daily_analysis_service
from app.services.review.market_review_generator import (
    ReviewGenerationLockedError,
    ReviewInputDataNotReadyError,
)
from app.services.review.stock_daily_analysis_service import input_hash

_TRADE_DATE = date(2026, 9, 1)
_CREATED_AT = datetime(2026, 9, 1, 16, 45, 0, tzinfo=timezone.utc)
_STOCK_CODE = "600519"

_SECTIONS = [
    PromptSection(key="intraday_review", title="盘面解读"),
    PromptSection(key="key_events", title="关键事件"),
    PromptSection(key="strategy", title="操作策略"),
    PromptSection(key="risk_lines", title="风险与止损"),
]


def _contents(**overrides: str) -> dict[str, str]:
    contents = {
        "intraday_review": "盘面内容",
        "key_events": "事件内容",
        "strategy": "策略内容",
        "risk_lines": "风险内容",
    }
    contents.update(overrides)
    return contents


def _structured(sections: dict[str, str] | None = None) -> dict:
    return {
        "trade_date": _TRADE_DATE.isoformat(),
        "stock_code": _STOCK_CODE,
        "stock_name": "贵州茅台",
        "sections": sections if sections is not None else _contents(),
    }


def _base_row(sections: dict[str, str] | None = None) -> object:
    row = SimpleNamespace(
        structured_output=_structured(sections),
        model="openai/gpt-4o",
        created_at=_CREATED_AT,
    )
    return row


_PROMPT_TEMPLATE = "请生成 {stock_name}（{stock_code}）{trade_date} 的每日个股分析：\n{section_instructions}"


def _patch_prompt_config() -> None:
    return patch.object(  # type: ignore[return-value]
        stock_daily_analysis_service,
        "load_prompt_config",
        lambda: SimpleNamespace(sections=_SECTIONS, user_prompt_template=_PROMPT_TEMPLATE),
    )


def _patch_lock(acquired: bool = True):
    @asynccontextmanager
    async def _fake_lock(*args: object, **kwargs: object):
        yield acquired

    return patch.object(stock_daily_analysis_service, "redis_lock", _fake_lock)


def _patch_market_data(
    kline_bars: list | None = None,
    quote: dict | None = None,
    stock_name: str | None = "贵州茅台",
):
    stock = SimpleNamespace(stock_name=stock_name) if stock_name else None
    return (
        patch(
            "app.services.market.stock_service.get_stock_by_code",
            AsyncMock(return_value=stock),
        ),
        patch(
            "app.services.market.kline_service.get_kline_by_code",
            AsyncMock(return_value=(kline_bars or [], len(kline_bars or []))),
        ),
        patch(
            "app.services.market.stock_service.get_stock_quote",
            AsyncMock(return_value=quote),
        ),
    )


def _kline_bar(day: int) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=date(2026, 8, day),
        open=1500.0,
        high=1520.0,
        low=1490.0,
        close=1510.0,
        change_pct=0.67,
        volume=30000,
        amount=450000000.0,
    )


def _patch_agent(
    sections: dict[str, str], model: str = "openai/gpt-4o", latency_ms: int = 150
):
    return patch(
        "app.agent.skills.stock_daily_analysis_agent.run_skill",
        AsyncMock(return_value=(sections, model, latency_ms)),
    )


@pytest.mark.unit
class TestInputHash:
    def test_deterministic_for_same_inputs(self) -> None:
        assert input_hash(_STOCK_CODE, _TRADE_DATE, _SECTIONS) == input_hash(
            _STOCK_CODE, _TRADE_DATE, _SECTIONS
        )

    def test_varies_by_stock_code(self) -> None:
        assert input_hash(_STOCK_CODE, _TRADE_DATE, _SECTIONS) != input_hash(
            "000001", _TRADE_DATE, _SECTIONS
        )

    def test_varies_by_trade_date(self) -> None:
        assert input_hash(_STOCK_CODE, _TRADE_DATE, _SECTIONS) != input_hash(
            _STOCK_CODE, date(2026, 8, 29), _SECTIONS
        )

    def test_varies_by_section_keys(self) -> None:
        altered = [PromptSection(key="extra", title="新分区"), *_SECTIONS]
        assert input_hash(_STOCK_CODE, _TRADE_DATE, _SECTIONS) != input_hash(
            _STOCK_CODE, _TRADE_DATE, altered
        )


@pytest.mark.unit
class TestGenerateStockAnalysis:
    @pytest.mark.asyncio
    async def test_returns_cached_without_lock_when_exists(self) -> None:
        lock_mock = _patch_lock(acquired=False)
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row()),
            ),
            _patch_prompt_config(),
            lock_mock,
        ):
            result = await stock_daily_analysis_service.generate_stock_analysis(
                AsyncMock(), _STOCK_CODE, trade_date=_TRADE_DATE
            )

        assert result.cached is True
        assert result.stock_code == _STOCK_CODE
        assert result.stock_name == "贵州茅台"
        assert result.sections[0].title == "盘面解读"
        assert result.sections[0].content == "盘面内容"

    @pytest.mark.asyncio
    async def test_raises_when_lock_held_and_no_cache(self) -> None:
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_prompt_config(),
            _patch_lock(acquired=False),
            pytest.raises(ReviewGenerationLockedError),
        ):
            await stock_daily_analysis_service.generate_stock_analysis(
                AsyncMock(), _STOCK_CODE, trade_date=_TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_raises_not_ready_when_kline_and_quote_missing(self) -> None:
        stock_patch, kline_patch, quote_patch = _patch_market_data(
            kline_bars=[], quote=None
        )
        session = AsyncMock()
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_prompt_config(),
            _patch_lock(),
            stock_patch,
            kline_patch,
            quote_patch,
            pytest.raises(ReviewInputDataNotReadyError),
        ):
            await stock_daily_analysis_service.generate_stock_analysis(
                session, _STOCK_CODE, trade_date=_TRADE_DATE
            )

        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generates_with_degraded_kline_and_persists_stock_code(self) -> None:
        """K 线缺失但行情快照在时降级生成；stock_code 须独立落列。"""
        insert_mock = AsyncMock(return_value=1)
        stock_patch, kline_patch, quote_patch = _patch_market_data(
            kline_bars=[], quote={"price": 1510.0, "change_pct": 0.67}
        )
        session = AsyncMock()
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_prompt_config(),
            _patch_lock(),
            stock_patch,
            kline_patch,
            quote_patch,
            _patch_agent(_contents()),
            patch(
                "app.repositories.review.ai_analysis_repository.insert_result",
                insert_mock,
            ),
        ):
            result = await stock_daily_analysis_service.generate_stock_analysis(
                session, _STOCK_CODE, trade_date=_TRADE_DATE
            )

        assert result.cached is False
        assert result.model == "openai/gpt-4o"
        assert [s.key for s in result.sections] == [
            "intraday_review",
            "key_events",
            "strategy",
            "risk_lines",
        ]
        insert_mock.assert_awaited_once()
        _, kwargs = insert_mock.await_args
        assert kwargs["stock_code"] == _STOCK_CODE
        assert kwargs["skill_id"] == "stock-daily-analysis"
        structured = kwargs["structured"]
        assert structured["stock_code"] == _STOCK_CODE
        assert structured["trade_date"] == _TRADE_DATE.isoformat()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_soft_fills_missing_section_with_empty_string(self) -> None:
        """LLM 漏输出分区时软校验兜底空串，不阻断落库。"""
        insert_mock = AsyncMock(return_value=1)
        partial = _contents(intraday_review="", risk_lines="")
        partial.pop("risk_lines")
        stock_patch, kline_patch, quote_patch = _patch_market_data(
            kline_bars=[_kline_bar(29)], quote={"price": 1510.0}
        )
        session = AsyncMock()
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_prompt_config(),
            _patch_lock(),
            stock_patch,
            kline_patch,
            quote_patch,
            _patch_agent(partial),
            patch(
                "app.repositories.review.ai_analysis_repository.insert_result",
                insert_mock,
            ),
        ):
            result = await stock_daily_analysis_service.generate_stock_analysis(
                session, _STOCK_CODE, trade_date=_TRADE_DATE
            )

        by_key = {s.key: s.content for s in result.sections}
        assert by_key["intraday_review"] == ""
        assert by_key["risk_lines"] == ""
        assert by_key["strategy"] == "策略内容"
        insert_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_regenerate_bypasses_cache(self) -> None:
        stock_patch, kline_patch, quote_patch = _patch_market_data(
            kline_bars=[_kline_bar(29)], quote={"price": 1510.0}
        )
        insert_mock = AsyncMock(return_value=1)
        session = AsyncMock()
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row()),
            ),
            _patch_prompt_config(),
            _patch_lock(),
            stock_patch,
            kline_patch,
            quote_patch,
            _patch_agent(_contents()),
            patch(
                "app.repositories.review.ai_analysis_repository.insert_result",
                insert_mock,
            ),
        ):
            result = await stock_daily_analysis_service.generate_stock_analysis(
                session, _STOCK_CODE, trade_date=_TRADE_DATE, regenerate=True
            )

        assert result.cached is False
        insert_mock.assert_awaited_once()


@pytest.mark.unit
class TestGetStockAnalysis:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cache(self) -> None:
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_prompt_config(),
        ):
            result = await stock_daily_analysis_service.get_stock_analysis(
                AsyncMock(), _STOCK_CODE, trade_date=_TRADE_DATE
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_builds_response_from_cached_row(self) -> None:
        row = _base_row()
        with (
            patch(
                "app.repositories.review.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=row),
            ),
            _patch_prompt_config(),
        ):
            result = await stock_daily_analysis_service.get_stock_analysis(
                AsyncMock(), _STOCK_CODE, trade_date=_TRADE_DATE
            )

        assert result is not None
        assert result.cached is True
        assert result.generated_at == _CREATED_AT
        assert result.model == "openai/gpt-4o"
        assert result.trade_date == _TRADE_DATE
        assert {s.key for s in result.sections} == {
            "intraday_review",
            "key_events",
            "strategy",
            "risk_lines",
        }


@pytest.mark.unit
class TestActiveWatchStockCodes:
    @pytest.mark.asyncio
    async def test_returns_distinct_codes(self) -> None:
        session = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalars.return_value = ["600519", "000001"]
        session.execute = AsyncMock(return_value=execute_result)

        codes = await stock_daily_analysis_service.list_active_watch_stock_codes(
            session
        )

        assert codes == ["600519", "000001"]
