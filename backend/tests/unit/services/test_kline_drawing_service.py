"""K 线画线服务单测：锚点校验（纯函数）+ AI 画线集多租户隔离（sqlite）。"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.kline_drawing import AiKlineDrawing, UserKlineDrawing
from app.models.user import User
from app.schemas.drawing import (
    AiKlineDrawingAdoptRequest,
    AiKlineDrawingItemSchema,
)
from app.services.market.kline_drawing_service import (
    KlineDrawingService,
    _format_price,
    _validate_anchors,
)

pytestmark = pytest.mark.unit


def _anchor(date: str, price: float) -> dict:
    return {"date": date, "price": price}


# ---------- _format_price ----------


def test_format_price_strips_trailing_zeros() -> None:
    assert _format_price(1520.0) == "1520"
    assert _format_price(10.50) == "10.5"
    assert _format_price(3.14) == "3.14"


# ---------- _validate_anchors ----------


def test_validate_anchors_accepts_trendline() -> None:
    _validate_anchors("trendline", [_anchor("2026-09-01", 10.0), _anchor("2026-09-10", 12.5)])


def test_validate_anchors_wrong_count() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("trendline", [_anchor("2026-09-01", 10.0)])
    with pytest.raises(BadRequestError):
        _validate_anchors("hline", [_anchor("", 10.0), _anchor("", 11.0)])


def test_validate_anchors_non_finite_price() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("hline", [{"date": "", "price": float("nan")}])


def test_validate_anchors_hline_rejects_date() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("hline", [_anchor("2026-09-01", 10.0)])


def test_validate_anchors_bad_date() -> None:
    with pytest.raises(BadRequestError):
        _validate_anchors("box", [_anchor("2026/09/01", 10.0), _anchor("2026-09-10", 12.0)])
    with pytest.raises(BadRequestError):
        _validate_anchors("box", [_anchor("", 10.0), _anchor("2026-09-10", 12.0)])


# ---------- serialize_user_drawings_context（需求 4.4 读协议） ----------
# ---------- AI 画线 item schema 冒烟（payload camelCase 往返） ----------


def test_ai_item_schema_roundtrip() -> None:
    item = AiKlineDrawingItemSchema.model_validate(
        {
            "drawingType": "trendline",
            "anchors": [
                {"date": "2026-09-01", "price": 10.0},
                {"date": "2026-09-10", "price": 12.0},
            ],
            "label": "上升趋势线",
            "reason": "低点抬高",
        }
    )
    assert item.drawing_type == "trendline"
    assert item.anchors[1].price == 12.0




# ---------- AI 画线集多租户隔离（per-user 私有工作区，sqlite） ----------


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, AiKlineDrawing.__table__, UserKlineDrawing.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


def _ai_item(label: str = "压力位") -> AiKlineDrawingItemSchema:
    return AiKlineDrawingItemSchema.model_validate(
        {
            "drawingType": "trendline",
            "anchors": [
                {"date": "2026-09-01", "price": 10.0},
                {"date": "2026-09-10", "price": 12.0},
            ],
            "label": label,
            "reason": "两次低点连线",
        }
    )


async def _seed_user(session: AsyncSession, username: str) -> int:
    user = User(username=username, email=f"{username}@x.com", password_hash="x", role="user")
    session.add(user)
    await session.flush()
    return user.id


@pytest.mark.asyncio
async def test_ai_group_isolated_between_users(session: AsyncSession) -> None:
    """A 用户写入的 AI 画线组对 B 用户不可见（多租户隔离）。"""
    service = KlineDrawingService(session)
    user_a = await _seed_user(session, "alice")
    user_b = await _seed_user(session, "bob")

    await service.upsert_ai_group(
        user_id=user_a,
        target_type="stock",
        target_code="600519",
        period="daily",
        skill_id="kline-smart-drawing",
        trade_date=date(2026, 9, 10),
        drawings=[_ai_item()],
    )

    seen_a = await service.list_drawings(user_a, "stock", "600519")
    seen_b = await service.list_drawings(user_b, "stock", "600519")
    assert len(seen_a.ai) == 1 and seen_a.ai[0].drawings[0].label == "压力位"
    assert seen_b.ai == []


@pytest.mark.asyncio
async def test_same_target_per_user_independent_groups(session: AsyncSession) -> None:
    """两用户同标的同周期各自独立成组，互不覆盖。"""
    service = KlineDrawingService(session)
    user_a = await _seed_user(session, "alice")
    user_b = await _seed_user(session, "bob")

    for user_id, label in ((user_a, "A 的趋势线"), (user_b, "B 的趋势线")):
        await service.upsert_ai_group(
            user_id=user_id,
            target_type="stock",
            target_code="600519",
            period="daily",
            skill_id="kline-smart-drawing",
            trade_date=date(2026, 9, 10),
            drawings=[_ai_item(label)],
        )

    seen_a = await service.list_drawings(user_a, "stock", "600519")
    seen_b = await service.list_drawings(user_b, "stock", "600519")
    assert [item.label for item in seen_a.ai[0].drawings] == ["A 的趋势线"]
    assert [item.label for item in seen_b.ai[0].drawings] == ["B 的趋势线"]

    # B 清空不影响 A
    await service.clear_ai_group(user_b, "stock", "600519", "daily")
    assert len((await service.list_drawings(user_a, "stock", "600519")).ai) == 1
    assert (await service.list_drawings(user_b, "stock", "600519")).ai == []


@pytest.mark.asyncio
async def test_adopt_scoped_to_owner(session: AsyncSession) -> None:
    """采纳只从本人 AI 画线组定位；B 无组时 404。"""
    service = KlineDrawingService(session)
    user_a = await _seed_user(session, "alice")
    user_b = await _seed_user(session, "bob")
    await service.upsert_ai_group(
        user_id=user_a,
        target_type="stock",
        target_code="600519",
        period="daily",
        skill_id="kline-smart-drawing",
        trade_date=date(2026, 9, 10),
        drawings=[_ai_item()],
    )

    with pytest.raises(NotFoundError):
        await service.adopt_ai_drawing(
            user_b,
            AiKlineDrawingAdoptRequest(
                targetType="stock",
                targetCode="600519",
                period="daily",
                label="压力位",
                style={"color": "#f0b429", "lineStyle": "solid", "width": 2},
            ),
        )
    adopted = await service.adopt_ai_drawing(
        user_a,
        AiKlineDrawingAdoptRequest(
            targetType="stock",
            targetCode="600519",
            period="daily",
            label="压力位",
            style={"color": "#f0b429", "lineStyle": "solid", "width": 2},
        ),
    )
    assert adopted.drawing_type == "trendline"
