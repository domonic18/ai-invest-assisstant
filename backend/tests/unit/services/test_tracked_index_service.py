"""跟踪指数配置服务单测：启用校验三态 + CRUD 委派。"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.tracked_index import TrackedIndexConfig
from app.schemas.tracked_index import TrackedIndexCreate
from app.services.admin.tracked_index_service import TrackedIndexService


def _row(**overrides) -> TrackedIndexConfig:
    row = TrackedIndexConfig(
        id=1,
        index_code="GC00Y",
        index_name="COMEX 黄金",
        market_category="全球",
        data_source="eastmoney",
        sort_order=5,
        is_enabled=True,
        created_at=datetime(2026, 9, 1),
        updated_at=datetime(2026, 9, 1),
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


async def _fake_refresh(obj) -> None:
    """模拟 DB 服务端默认值回填（未 flush 时 ORM default 不生效）。"""
    if getattr(obj, "created_at", None) is None:
        obj.created_at = datetime(2026, 9, 1)
    obj.updated_at = datetime(2026, 9, 1)


def _service() -> TrackedIndexService:
    service = TrackedIndexService(AsyncMock())
    service.repo = MagicMock()
    service.repo.add = MagicMock()
    service.repo.refresh = AsyncMock(side_effect=_fake_refresh)
    service.repo.get = AsyncMock(return_value=None)
    service.repo.get_by_code = AsyncMock(return_value=None)
    service.repo.list_ordered = AsyncMock(return_value=[])
    service.repo.latest_quotes = AsyncMock(return_value={})
    service.repo.delete = AsyncMock()
    return service


@pytest.mark.unit
class TestValidateEnable:
    @pytest.mark.parametrize(
        ("code", "category", "source", "ok"),
        [
            ("GC00Y", "全球", "eastmoney", True),
            ("GC00Y", "全球", "sina", False),  # 来源不匹配
            ("BTC", "全球", "eastmoney", False),  # 全球未支持
            ("sh000001", "A股", "sina", True),
            ("sh000001", "A股", "eastmoney", False),  # A 股非法来源
            ("bk0800", "A股", "sina", False),  # A 股非法代码
        ],
    )
    def test_matrix(self, code: str, category: str, source: str, ok: bool) -> None:
        if ok:
            TrackedIndexService._validate_enable(code, category, source)
        else:
            with pytest.raises(ValueError, match="无数据源的指标不允许启用"):
                TrackedIndexService._validate_enable(code, category, source)

    def test_unknown_category_rejected(self) -> None:
        with pytest.raises(ValueError, match="market_category"):
            TrackedIndexService._validate_enable("GC00Y", "美股", "eastmoney")


@pytest.mark.unit
class TestCrud:
    async def test_create_enabled_valid(self) -> None:
        service = _service()
        data = TrackedIndexCreate(
            index_code="GC00Y",
            index_name="COMEX 黄金",
            market_category="全球",
            data_source="eastmoney",
            is_enabled=True,
        )
        service.repo.add.side_effect = lambda obj: setattr(obj, "id", 1)
        result = await service.create_index(data)
        assert result.index_code == "GC00Y"

    async def test_disabled_allows_any_code(self) -> None:
        """停用态允许保存任意代码（不触发启用校验）。"""
        service = _service()
        data = TrackedIndexCreate(
            index_code="BTC",
            index_name="比特币",
            market_category="全球",
            data_source="eastmoney",
            is_enabled=False,
        )
        service.repo.add.side_effect = lambda obj: setattr(obj, "id", 1)
        with patch.object(TrackedIndexService, "_validate_enable") as mock_validate:
            result = await service.create_index(data)
        mock_validate.assert_not_called()
        assert result.is_enabled is False

    async def test_create_duplicate_code_rejected(self) -> None:
        service = _service()
        service.repo.get_by_code = AsyncMock(return_value=_row())
        data = TrackedIndexCreate(
            index_code="GC00Y",
            index_name="COMEX 黄金",
            market_category="全球",
            data_source="eastmoney",
        )
        with pytest.raises(ValueError, match="已存在"):
            await service.create_index(data)

    async def test_toggle_enable_validates(self) -> None:
        service = _service()
        row = _row(is_enabled=False, index_code="BTC")
        service.repo.get = AsyncMock(return_value=row)
        with pytest.raises(ValueError, match="无数据源的指标不允许启用"):
            await service.toggle_index(1)

    async def test_toggle_disable_skips_validation(self) -> None:
        service = _service()
        row = _row(is_enabled=True)
        service.repo.get = AsyncMock(return_value=row)
        result = await service.toggle_index(1)
        assert result.is_enabled is False

    async def test_delete_missing_raises(self) -> None:
        service = _service()
        service.repo.get = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="不存在"):
            await service.delete_index(99)

    async def test_latest_quotes_merged_into_response(self) -> None:
        service = _service()
        service.repo.list_ordered = AsyncMock(return_value=[_row()])
        service.repo.latest_quotes = AsyncMock(
            return_value={
                "GC00Y": {
                    "close": 4363.6,
                    "change_pct": -1.21,
                    "trade_date": date(2026, 9, 1),
                }
            }
        )
        result = await service.list_indexes()
        assert result[0].latest_close == 4363.6
        assert result[0].latest_change_pct == -1.21
        assert result[0].latest_trade_date == date(2026, 9, 1)
