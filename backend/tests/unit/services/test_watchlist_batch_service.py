"""自选股批量导入与截图识别服务测试。"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.user import WatchlistBatchCreate, WatchlistBatchItemCreate
from app.services.user.screenshot_recognition_service import (
    ScreenshotValidationError,
    recognize_screenshot,
)
from app.services.user.watchlist_service import WatchlistService

pytestmark = pytest.mark.unit


def _make_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)

    @asynccontextmanager
    async def _nested():
        yield None

    session.begin_nested = MagicMock(side_effect=_nested)
    return session


def _make_group(group_id: int, name: str = "科技") -> MagicMock:
    group = MagicMock()
    group.id = group_id
    group.name = name
    return group


def _make_item(stock_code: str, group_id: int = 7) -> MagicMock:
    item = MagicMock()
    item.stock_code = stock_code
    item.group_id = group_id
    return item


def _batch(*codes: str, new_group: str = "截图导入") -> WatchlistBatchCreate:
    return WatchlistBatchCreate(
        items=[WatchlistBatchItemCreate(stock_code=code) for code in codes],
        new_group_name=new_group,
    )


@pytest.mark.asyncio
async def test_batch_add_creates_valid_and_flags_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session()
    service = WatchlistService(session)
    monkeypatch.setattr(
        "app.services.user.watchlist_service.StockRepository",
        lambda _s: SimpleNamespace(
            get_names_by_codes=AsyncMock(
                return_value={"600519": "贵州茅台", "000001": "平安银行"}
            )
        ),
    )
    _patch_groups(service)
    service.repo.get_by_user_and_stock = AsyncMock(return_value=None)

    created_rows: list[MagicMock] = []

    def _fake_add(row: MagicMock) -> None:
        row.id = len(created_rows) + 100
        row.created_at = datetime(2026, 9, 4, tzinfo=UTC)
        created_rows.append(row)

    service.repo.add = _fake_add

    result = await service.batch_add_items(SimpleNamespace(id=1), _batch("600519", "000001", "999999"))

    assert [item.stock_code for item in result.created] == ["600519", "000001"]
    assert all(item.group_id == 9 for item in result.created)
    assert result.invalid == ["999999"]
    assert result.duplicated == []
    # create_group 落库提交 + 批量新增统一提交
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_batch_add_reports_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _make_session()
    service = WatchlistService(session)
    monkeypatch.setattr(
        "app.services.user.watchlist_service.StockRepository",
        lambda _s: SimpleNamespace(
            get_names_by_codes=AsyncMock(return_value={"600519": "贵州茅台"})
        ),
    )
    _patch_groups(service)
    service.repo.get_by_user_and_stock = AsyncMock(
        side_effect=lambda _uid, code: _make_item(code, group_id=7)
    )

    result = await service.batch_add_items(SimpleNamespace(id=1), _batch("600519"))

    assert result.created == []
    assert len(result.duplicated) == 1
    assert result.duplicated[0].stock_code == "600519"
    assert result.duplicated[0].group_id == 7
    assert result.duplicated[0].group_name == "默认分组"


@pytest.mark.asyncio
async def test_batch_add_skips_duplicates_within_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session()
    service = WatchlistService(session)
    monkeypatch.setattr(
        "app.services.user.watchlist_service.StockRepository",
        lambda _s: SimpleNamespace(
            get_names_by_codes=AsyncMock(return_value={"600519": "贵州茅台"})
        ),
    )
    _patch_groups(service)
    _stub_item_repo_add(service)
    service.repo.get_by_user_and_stock = AsyncMock(return_value=None)

    result = await service.batch_add_items(SimpleNamespace(id=1), _batch("600519", "600519"))

    assert [item.stock_code for item in result.created] == ["600519"]


def _patch_groups(
    service: WatchlistService, default_group_id: int = 7, new_group_id: int = 9
) -> None:
    default = _make_group(default_group_id, name="默认分组")
    service.group_repo.count_by_user = AsyncMock(return_value=0)
    service.group_repo.get_by_name = AsyncMock(return_value=None)
    service.group_repo.get_by_user_and_id = AsyncMock(return_value=None)
    service.group_repo.get_default = AsyncMock(return_value=default)
    service.group_repo.list_by_user = AsyncMock(return_value=[default])
    service.group_repo.add = MagicMock()
    service.group_repo.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", new_group_id))


def _stub_item_repo_add(service: WatchlistService) -> None:
    """模拟落库分配主键与 created_at，跳过真实 refresh。"""

    def _fake_add(row: MagicMock) -> None:
        row.id = 100
        row.created_at = datetime(2026, 9, 4, tzinfo=UTC)

    service.repo.add = _fake_add
    service.repo.refresh = AsyncMock()


@pytest.mark.asyncio
async def test_recognize_rejects_unsupported_type() -> None:
    with pytest.raises(ScreenshotValidationError):
        await recognize_screenshot(MagicMock(), b"img", "image/gif")


@pytest.mark.asyncio
async def test_recognize_rejects_oversized_image() -> None:
    with pytest.raises(ScreenshotValidationError):
        await recognize_screenshot(MagicMock(), b"x" * (8 * 1024 * 1024 + 1), "image/png")


def _patch_recognition_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    names_by_code: dict[str, str],
    codes_by_name: dict[str, str],
    recognized: list,
) -> None:
    async def fake_run_skill(_session, _image):
        return recognized

    monkeypatch.setattr(
        "app.agent.skills.watchlist_screenshot_recognition.run_skill", fake_run_skill
    )
    monkeypatch.setattr(
        "app.services.user.screenshot_recognition_service.StockRepository",
        lambda _s: SimpleNamespace(
            get_names_by_codes=AsyncMock(return_value=names_by_code),
            get_codes_by_names=AsyncMock(return_value=codes_by_name),
        ),
    )


@pytest.mark.asyncio
async def test_recognize_cross_validates_with_stock_basic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agent.skills.watchlist_screenshot_recognition import RecognizedStock

    _patch_recognition_env(
        monkeypatch,
        names_by_code={"600519": "贵州茅台"},
        codes_by_name={},
        recognized=[
            RecognizedStock(code="600519", name="贵州茅台", confidence=0.98),
            RecognizedStock(code="300750", name="宁德时代", confidence=0.9),
        ],
    )

    items = await recognize_screenshot(MagicMock(), b"img", "image/png")

    assert len(items) == 2
    by_code = {item.stock_code: item for item in items}
    assert by_code["600519"].valid is True
    assert by_code["600519"].matched_name == "贵州茅台"
    assert by_code["300750"].valid is False


@pytest.mark.asyncio
async def test_recognize_falls_back_to_name_match(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent.skills.watchlist_screenshot_recognition import RecognizedStock

    _patch_recognition_env(
        monkeypatch,
        names_by_code={"600519": "贵州茅台"},
        codes_by_name={"贵州茅台": "600519"},
        recognized=[RecognizedStock(code="999999", name="贵州茅台", confidence=0.8)],
    )

    items = await recognize_screenshot(MagicMock(), b"img", "image/jpeg")

    assert len(items) == 1
    assert items[0].stock_code == "600519"
    assert items[0].valid is True
