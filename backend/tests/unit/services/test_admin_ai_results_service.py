"""后台 AI 结果管理服务单元测试（仓储 mock + 描述符提取验证）。"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, UnprocessableEntityError
from app.repositories.admin import ai_result_repository
from app.services.admin.ai_results import (
    SKILL_DESCRIPTORS,
    UNKNOWN,
    AdminAiResultService,
)
from app.services.review.limit_up_ai_service import (
    _input_hash as limit_up_input_hash,
)

_MARKET_SKILL = "market-daily-review"


def _row(
    *,
    skill_id: str = _MARKET_SKILL,
    input_hash: str | None = "hash-1",
    structured_output: dict | None = None,
    stock_code: str | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = 7
    row.skill_id = skill_id
    row.input_hash = input_hash
    row.structured_output = structured_output if structured_output is not None else {}
    row.stock_code = stock_code
    row.model = "anthropic/kimi"
    row.latency_ms = 59000
    row.status = "success"
    row.created_at = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)
    row.error_msg = None
    return row


def _service() -> AdminAiResultService:
    return AdminAiResultService(AsyncMock())


@pytest.mark.unit
class TestSkillRegistry:
    def test_four_skills_registered_with_unique_ids(self) -> None:
        skills = AdminAiResultService.list_skills()
        assert [s.skill_id for s in skills] == [d.skill_id for d in SKILL_DESCRIPTORS]
        assert len({s.skill_id for s in skills}) == len(skills)

    def test_chain_has_no_regenerate_entry(self) -> None:
        chain = next(
            s for s in AdminAiResultService.list_skills()
            if s.skill_id == "industry-chain-analysis"
        )
        assert chain.event_type is None
        assert chain.label


@pytest.mark.unit
class TestListResults:
    async def test_market_review_key_fields_and_prompt(self) -> None:
        service = _service()
        row = _row(structured_output={"trade_date": "2026-09-04"})
        with (
            patch.object(
                service.repo, "list_paginated", AsyncMock(return_value=([row], 1))
            ),
            patch.object(
                service.repo, "counts_by_hash", AsyncMock(return_value={"hash-1": 3})
            ),
        ):
            items, total = await service.list_results(_MARKET_SKILL)
        assert total == 1
        assert items[0].key_fields[0].name == "trade_date"
        assert items[0].key_fields[0].value == "2026-09-04"
        assert items[0].history_count == 3
        assert items[0].regenerate_prompt == "请重新生成 2026-09-04 的大盘每日复盘"

    async def test_stock_analysis_uses_physical_column_and_jsonb(self) -> None:
        service = _service()
        row = _row(
            skill_id="stock-daily-analysis",
            stock_code="600519",
            structured_output={
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "trade_date": "2026-09-04",
                "sections": {},
            },
        )
        with (
            patch.object(
                service.repo, "list_paginated", AsyncMock(return_value=([row], 1))
            ),
            patch.object(service.repo, "counts_by_hash", AsyncMock(return_value={})),
        ):
            items, _ = await service.list_results("stock-daily-analysis")
        values = {f.name: f.value for f in items[0].key_fields}
        assert values["stock_code"] == "600519"
        assert values["stock_name"] == "贵州茅台"
        assert items[0].regenerate_prompt == (
            "请重新生成 600519（2026-09-04）的每日个股分析"
        )

    async def test_limit_up_reverse_hash_recovers_trade_date(self) -> None:
        service = _service()
        trade_date = date(2026, 9, 4)
        row = _row(
            skill_id="limit-up-review",
            input_hash=limit_up_input_hash(trade_date),
            structured_output={"groups": []},
        )
        with (
            patch.object(
                service.repo, "list_paginated", AsyncMock(return_value=([row], 1))
            ),
            patch.object(service.repo, "counts_by_hash", AsyncMock(return_value={})),
            patch.object(
                service.repo,
                "min_created_at",
                AsyncMock(
                    return_value=datetime(2026, 9, 1, tzinfo=timezone.utc)
                ),
            ),
            patch("app.services.admin.ai_results.today_cn", return_value=date(2026, 9, 5)),
        ):
            items, _ = await service.list_results("limit-up-review")
        assert items[0].key_fields[0].value == "2026-09-04"
        assert items[0].regenerate_prompt == "请重新生成 2026-09-04 的涨停板块归因"

    async def test_chain_parses_input_hash(self) -> None:
        service = _service()
        row = _row(skill_id="industry-chain-analysis", input_hash="3:半导体:v2")
        with (
            patch.object(
                service.repo, "list_paginated", AsyncMock(return_value=([row], 1))
            ),
            patch.object(service.repo, "counts_by_hash", AsyncMock(return_value={})),
        ):
            items, _ = await service.list_results("industry-chain-analysis")
        values = {f.name: f.value for f in items[0].key_fields}
        assert values == {"user_id": "3", "industry": "半导体", "version": "v2"}
        assert items[0].regenerate_prompt is None

    async def test_missing_key_shows_unknown_and_suppresses_prompt(self) -> None:
        service = _service()
        row = _row(structured_output={})
        with (
            patch.object(
                service.repo, "list_paginated", AsyncMock(return_value=([row], 1))
            ),
            patch.object(service.repo, "counts_by_hash", AsyncMock(return_value={})),
        ):
            items, _ = await service.list_results(_MARKET_SKILL)
        assert items[0].key_fields[0].value == UNKNOWN
        assert items[0].regenerate_prompt is None

    async def test_unregistered_skill_rejected(self) -> None:
        with pytest.raises(UnprocessableEntityError):
            await _service().list_results("mystery-skill")


@pytest.mark.unit
class TestGetDetail:
    async def test_returns_structured_output(self) -> None:
        service = _service()
        row = _row(structured_output={"trade_date": "2026-09-04", "sections": {}})
        with patch.object(service.repo, "get_by_id", AsyncMock(return_value=row)):
            detail = await service.get_detail(7)
        assert detail.structured_output == {
            "trade_date": "2026-09-04",
            "sections": {},
        }
        assert detail.regenerate_prompt == "请重新生成 2026-09-04 的大盘每日复盘"

    async def test_unregistered_skill_falls_back_without_error(self) -> None:
        service = _service()
        row = _row(skill_id="mystery-skill", structured_output={"foo": 1})
        with patch.object(service.repo, "get_by_id", AsyncMock(return_value=row)):
            detail = await service.get_detail(7)
        assert detail.key_fields == []
        assert detail.structured_output == {"foo": 1}

    async def test_404_when_row_missing(self) -> None:
        with patch.object(
            ai_result_repository, "get_by_id", AsyncMock(return_value=None)
        ):
            with pytest.raises(NotFoundError):
                await _service().get_detail(404)


@pytest.mark.unit
class TestDelete:
    async def test_deletes_whole_hash_group_and_commits(self) -> None:
        service = _service()
        row = _row(input_hash="hash-1")
        with (
            patch.object(service.repo, "get_by_id", AsyncMock(return_value=row)),
            patch.object(
                service.repo, "delete_by_hash", AsyncMock(return_value=4)
            ) as mock_delete,
            patch.object(service.repo, "delete_by_id", AsyncMock()) as mock_delete_id,
        ):
            deleted = await service.delete(7)
        assert deleted == 4
        mock_delete.assert_awaited_once_with(
            service.session, skill_id=_MARKET_SKILL, input_hash="hash-1"
        )
        mock_delete_id.assert_not_awaited()
        service.session.commit.assert_awaited_once()

    async def test_null_hash_falls_back_to_single_row(self) -> None:
        service = _service()
        row = _row(input_hash=None)
        with (
            patch.object(service.repo, "get_by_id", AsyncMock(return_value=row)),
            patch.object(
                service.repo, "delete_by_id", AsyncMock(return_value=1)
            ) as mock_delete_id,
            patch.object(service.repo, "delete_by_hash", AsyncMock()) as mock_delete,
        ):
            deleted = await service.delete(7)
        assert deleted == 1
        mock_delete_id.assert_awaited_once_with(service.session, 7)
        mock_delete.assert_not_awaited()

    async def test_404_when_row_missing(self) -> None:
        with patch.object(
            ai_result_repository, "get_by_id", AsyncMock(return_value=None)
        ):
            with pytest.raises(NotFoundError):
                await _service().delete(404)
