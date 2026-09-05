"""AdminMarketReviewService 复盘管理契约测试（mock 仓储与生成器函数）。"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.core.prompt_loader import PromptSection
from app.services.admin.market_review import AdminMarketReviewService
from app.services.review.market_review_generator import ReviewNotFoundError

_TRADE_DATE = date(2026, 9, 4)
_GENERATED_AT = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

_SECTIONS = [PromptSection(key="overview", title="AI 大盘综述")]


def _prompt_config() -> SimpleNamespace:
    return SimpleNamespace(sections=_SECTIONS)


def _row_mock() -> MagicMock:
    row = MagicMock()
    row.structured_output = {"trade_date": _TRADE_DATE.isoformat(), "sections": {}}
    row.model = "anthropic/kimi"
    row.latency_ms = 59000
    row.created_at = _GENERATED_AT
    return row


@pytest.fixture
def service() -> AdminMarketReviewService:
    return AdminMarketReviewService(AsyncMock())


@pytest.mark.unit
class TestListReviews:
    @pytest.mark.asyncio
    async def test_assembles_items_with_counts(self, service) -> None:
        rows = [_row_mock()]
        with (
            patch.object(
                service.repo,
                "list_paginated",
                AsyncMock(return_value=(rows, 1)),
            ) as list_mock,
            patch.object(
                service.repo,
                "counts_by_date",
                AsyncMock(return_value={_TRADE_DATE: 3}),
            ),
            patch.object(
                service.repo,
                "user_copy_counts",
                AsyncMock(return_value={_TRADE_DATE: 1}),
            ),
        ):
            items, total = await service.list_reviews(page=2, page_size=10)

        assert total == 1
        item = items[0]
        assert item.trade_date == _TRADE_DATE
        assert item.model == "anthropic/kimi"
        assert item.latency_ms == 59000
        assert item.generated_at == _GENERATED_AT
        assert item.history_count == 3
        assert item.user_copy_count == 1
        list_mock.assert_awaited_once_with(
            service.session,
            skill_id="market-daily-review",
            page=2,
            page_size=10,
            start_date=None,
            end_date=None,
        )

    @pytest.mark.asyncio
    async def test_skips_rows_without_trade_date(self, service) -> None:
        dirty = _row_mock()
        dirty.structured_output = None
        with (
            patch.object(
                service.repo, "list_paginated", AsyncMock(return_value=([dirty], 1))
            ),
            patch.object(service.repo, "counts_by_date", AsyncMock(return_value={})),
            patch.object(service.repo, "user_copy_counts", AsyncMock(return_value={})),
        ):
            items, total = await service.list_reviews()
        assert items == []
        assert total == 1


@pytest.mark.unit
class TestGetDetail:
    @pytest.mark.asyncio
    async def test_returns_base_response(self, service) -> None:
        response = AsyncMock()
        base = SimpleNamespace(response=response)
        with (
            patch(
                "app.services.admin.market_review._load_base_review",
                AsyncMock(return_value=base),
            ),
            patch(
                "app.services.admin.market_review.load_prompt_config",
                lambda: _prompt_config(),
            ),
        ):
            result = await service.get_detail(_TRADE_DATE)
        assert result is response

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self, service) -> None:
        with (
            patch(
                "app.services.admin.market_review._load_base_review",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.admin.market_review.load_prompt_config",
                lambda: _prompt_config(),
            ),
            pytest.raises(ReviewNotFoundError),
        ):
            await service.get_detail(_TRADE_DATE)


@pytest.mark.unit
class TestCreateAndUpdate:
    @pytest.mark.asyncio
    async def test_create_asserts_trading_day_and_persists(self, service) -> None:
        response = AsyncMock()
        sections = {"overview": "综述", "risk_advice": "风险"}
        with (
            patch(
                "app.services.admin.market_review.assert_trading_day",
                AsyncMock(),
            ) as assert_mock,
            patch(
                "app.services.admin.market_review.persist_market_review_result",
                AsyncMock(return_value=response),
            ) as persist_mock,
        ):
            result = await service.create_manual(_TRADE_DATE, sections)

        assert result is response
        assert_mock.assert_awaited_once_with(service.session, _TRADE_DATE)
        persist_mock.assert_awaited_once_with(
            service.session, trade_date=_TRADE_DATE, contents=sections, model="manual"
        )

    @pytest.mark.asyncio
    async def test_update_requires_existing_base(self, service) -> None:
        with (
            patch(
                "app.services.admin.market_review._load_base_review",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.admin.market_review.load_prompt_config",
                lambda: _prompt_config(),
            ),
            pytest.raises(ReviewNotFoundError),
        ):
            await service.update_sections(_TRADE_DATE, {"overview": "x"})

    @pytest.mark.asyncio
    async def test_update_persists_new_record(self, service) -> None:
        response = AsyncMock()
        sections = {"overview": "新综述"}
        with (
            patch(
                "app.services.admin.market_review._load_base_review",
                AsyncMock(return_value=AsyncMock()),
            ),
            patch(
                "app.services.admin.market_review.load_prompt_config",
                lambda: _prompt_config(),
            ),
            patch(
                "app.services.admin.market_review.persist_market_review_result",
                AsyncMock(return_value=response),
            ) as persist_mock,
        ):
            result = await service.update_sections(_TRADE_DATE, sections)

        assert result is response
        persist_mock.assert_awaited_once_with(
            service.session, trade_date=_TRADE_DATE, contents=sections, model="manual"
        )


@pytest.mark.unit
class TestDelete:
    @pytest.mark.asyncio
    async def test_commits_and_returns_count(self, service) -> None:
        with patch.object(
            service.repo, "delete_by_date", AsyncMock(return_value=4)
        ) as delete_mock:
            deleted = await service.delete(_TRADE_DATE)
        assert deleted == 4
        delete_mock.assert_awaited_once_with(
            service.session, skill_id="market-daily-review", trade_date=_TRADE_DATE
        )
        service.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_nothing_deleted(self, service) -> None:
        with (
            patch.object(service.repo, "delete_by_date", AsyncMock(return_value=0)),
            pytest.raises(ReviewNotFoundError),
        ):
            await service.delete(_TRADE_DATE)
        service.session.commit.assert_not_awaited()


@pytest.mark.unit
class TestSectionDefinitions:
    def test_maps_key_and_title(self) -> None:
        with patch(
            "app.services.admin.market_review.load_prompt_config",
            lambda: _prompt_config(),
        ):
            definitions = AdminMarketReviewService.section_definitions()
        assert [d.key for d in definitions] == ["overview"]
        assert [d.title for d in definitions] == ["AI 大盘综述"]
