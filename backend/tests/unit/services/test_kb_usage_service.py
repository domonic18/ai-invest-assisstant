"""usage_service 单测：token 分项聚合、source 过滤、ASR 对照与成本。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.clock import CN_TZ
from app.services.kb import usage_service
from app.services.quota.constants import (
    FEATURE_KB_CLEAN,
    FEATURE_KB_EMBED,
    FEATURE_KB_EXTRACT,
    FEATURE_KB_VISION,
)


def _result(rows: list) -> MagicMock:
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    return result


def _session(ledger_rows: list, media_rows: list, prices: dict) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_result(ledger_rows), _result(media_rows)]
    )
    session.get = AsyncMock(
        return_value=SimpleNamespace(unit_prices=prices)
    )
    return session


def _ledger_rows() -> list:
    return [
        ("kb_clean", "minimax-m3", 1000, 500, 1500, {"sourceId": 1}),
        ("kb_clean", "minimax-m3", 2000, 1000, 3000, {"sourceId": 1}),
        ("kb_extract", "minimax-m3", 3000, 2000, 5000, {"sourceId": 1}),
        ("kb_vision", "glm-4v", 800, 400, 1200, {"sourceId": 1}),
        ("kb_vision", "glm-4v", 900, 300, 1200, {"sourceId": 1}),
        ("kb_embed", "embedding-3", 5000, 0, 5000, {"sourceId": 1}),
    ]


def _media_rows() -> list:
    # (duration_seconds, process_meta)：未转写行无 audio_seconds 跳过
    return [
        (3600, {"audio_seconds": 3550.0}),
        (1800, {"audio_seconds": 1810.5}),
        (600, {}),
        (None, {"audio_seconds": 100.0}),
    ]


@pytest.mark.unit
class TestGetUsage:
    async def test_aggregates_tokens_asr_and_costs(self) -> None:
        session = _session(
            _ledger_rows(),
            _media_rows(),
            {"asrPerHour": 0.3, "vlmPerImage": 0.02},
        )
        result = await usage_service.get_usage(session)
        by_feature = {item.feature: item for item in result.token_items}
        clean = by_feature[FEATURE_KB_CLEAN]
        assert clean.calls == 2 and clean.total_tokens == 4500
        assert clean.estimated_cost is None
        vision = by_feature[FEATURE_KB_VISION]
        assert vision.calls == 2 and vision.estimated_cost == 0.04
        embed = by_feature[FEATURE_KB_EMBED]
        assert embed.model_name == "embedding-3" and embed.total_tokens == 5000
        assert by_feature[FEATURE_KB_EXTRACT].total_tokens == 5000
        # 分项按管线顺序（清洗→抽取→视觉→嵌入）输出
        assert [i.feature for i in result.token_items] == [
            FEATURE_KB_CLEAN,
            FEATURE_KB_EXTRACT,
            FEATURE_KB_VISION,
            FEATURE_KB_EMBED,
        ]
        asr = result.asr
        assert asr.media_count == 3
        assert asr.audio_seconds == 5460.5
        assert asr.estimated_seconds == 5400
        assert asr.cost == pytest.approx(0.455)
        assert asr.cost_per_hour == 0.3
        # 清洗 token 预估（字符折算）vs 台账实际
        assert result.clean_tokens_predicted == 9600 + 4800
        assert result.clean_tokens_actual == 4500
        assert result.total_cost == pytest.approx(0.495)

    async def test_source_filter_uses_detail_context(self) -> None:
        ledger = _ledger_rows() + [
            ("kb_clean", "minimax-m3", 999, 1, 1000, {"sourceId": 2}),
            ("kb_extract", "minimax-m3", 999, 1, 1000, None),
        ]
        session = _session(ledger, _media_rows(), {"asrPerHour": 0.3})
        result = await usage_service.get_usage(session, source_id=1)
        clean = {i.feature: i for i in result.token_items}[FEATURE_KB_CLEAN]
        assert clean.total_tokens == 4500  # sourceId=2 与无上下文行均不计
        assert all(i.total_tokens <= 5000 for i in result.token_items)

    async def test_missing_prices_yield_null_costs(self) -> None:
        session = _session(_ledger_rows(), _media_rows(), {})
        result = await usage_service.get_usage(session)
        assert result.asr.cost is None and result.asr.cost_per_hour is None
        vision = {i.feature: i for i in result.token_items}[FEATURE_KB_VISION]
        assert vision.estimated_cost is None
        assert result.total_cost == 0.0


@pytest.mark.unit
class TestRangeBounds:
    def test_dates_map_to_cn_calendar_bounds(self) -> None:
        start, end = usage_service._range_bounds(
            date(2026, 9, 1), date(2026, 9, 21)
        )
        assert start is not None and start.tzinfo is CN_TZ
        assert start.hour == 0 and start.day == 1
        # 截止日按闭区间 → 次日零点开区间
        assert end is not None and end.day == 22 and end.hour == 0

    def test_absent_dates_yield_no_bounds(self) -> None:
        assert usage_service._range_bounds(None, None) == (None, None)
