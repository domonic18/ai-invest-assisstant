"""Unit tests for limit-up AI attribution service."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import limit_up_ai_service
from app.services.limit_up_ai_service import (
    AttributionGroup,
    LimitUpAttributionContent,
)
from app.services.market_review_service import NonTradingDayError

_TRADE_DATE = date(2026, 7, 20)


def _execute_returning(row):
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    return result


def _content_dict() -> dict:
    return {
        "groups": [
            {"theme": "电力改革", "reason": "政策催化", "stock_codes": ["000001"]}
        ],
        "stock_themes": {"000001": ["电力改革"]},
    }


@pytest.mark.unit
class TestValidate:
    def test_filters_hallucinated_codes_and_dedupes(self) -> None:
        content = LimitUpAttributionContent(
            groups=[
                AttributionGroup(
                    theme="A", reason="r1", stock_codes=["000001", "999999"]
                ),
                AttributionGroup(
                    theme="B", reason="r2", stock_codes=["000001", "000002"]
                ),
            ],
            stock_themes={"000001": ["A"], "999999": ["X"]},
        )

        result = limit_up_ai_service._validate(content, {"000001", "000002"})

        # 幻觉代码剔除 + 跨组去重（000001 已分入 A 组）
        assert [group.stock_codes for group in result.groups] == [
            ["000001"],
            ["000002"],
        ]
        assert result.stock_themes == {"000001": ["A"]}

    def test_drops_groups_left_empty_after_filtering(self) -> None:
        content = LimitUpAttributionContent(
            groups=[AttributionGroup(theme="A", reason="r", stock_codes=["999999"])]
        )

        result = limit_up_ai_service._validate(content, {"000001"})

        assert result.groups == []


@pytest.mark.unit
class TestGetCachedAttribution:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cached_row(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)

        assert (
            await limit_up_ai_service.get_cached_attribution(session, _TRADE_DATE)
            is None
        )

    @pytest.mark.asyncio
    async def test_returns_parsed_content(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(
            {"structured_output": _content_dict()}
        )

        result = await limit_up_ai_service.get_cached_attribution(
            session, _TRADE_DATE
        )

        assert result is not None
        assert result.groups[0].theme == "电力改革"
        assert result.stock_themes == {"000001": ["电力改革"]}


@pytest.mark.unit
class TestGenerateAttribution:
    @pytest.mark.asyncio
    async def test_rejects_non_trading_day(self) -> None:
        with (
            patch(
                "app.services.market_service.is_trading_day",
                AsyncMock(return_value=False),
            ),
            pytest.raises(NonTradingDayError),
        ):
            await limit_up_ai_service.generate_attribution(AsyncMock(), _TRADE_DATE)

    @pytest.mark.asyncio
    async def test_returns_cached_without_llm(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(
            {"structured_output": _content_dict()}
        )

        with patch(
            "app.services.market_service.is_trading_day", AsyncMock(return_value=True)
        ):
            result = await limit_up_ai_service.generate_attribution(
                session, _TRADE_DATE
            )

        assert result.groups[0].theme == "电力改革"

    @pytest.mark.asyncio
    async def test_raises_when_pool_empty(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)  # 无缓存

        with (
            patch(
                "app.services.market_service.is_trading_day",
                AsyncMock(return_value=True),
            ),
            patch(
                "app.services.market_service.get_limit_up",
                AsyncMock(return_value=MagicMock(items=[])),
            ),
            pytest.raises(ValueError, match="无涨停数据"),
        ):
            await limit_up_ai_service.generate_attribution(session, _TRADE_DATE)
