"""交易 Agent 计划/选股干预服务契约测试（批次 7：create/cancel/移出；D29 计划视图）。"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.agent_trading import AgentTradePlan
from app.services.trading import agent_plan_ops

_PLAN_DATE = date(2026, 7, 15)
_AK = "short-line"


def _session_with_scalars(results: list) -> AsyncMock:
    """scalar 调用按序出栈（主数据存在性 → 计划行查找）。"""
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=results)
    return session


def _plan_row(status: str = "active") -> MagicMock:
    row = MagicMock()
    row.status = status
    row.agent_key = _AK
    return row


@pytest.mark.unit
class TestCreatePlan:
    @pytest.mark.asyncio
    async def test_rejects_unknown_plan_type(self) -> None:
        with pytest.raises(BadRequestError, match="plan_type"):
            await agent_plan_ops.create_plan(
                AsyncMock(),
                _AK,
                plan_date=_PLAN_DATE,
                stock_code="600000",
                plan_type="hold",
                strategy="s",
                stop_loss=9.5,
                position_pct=10,
                basis="b",
            )

    @pytest.mark.asyncio
    async def test_buy_requires_buy_zone(self) -> None:
        with pytest.raises(BadRequestError, match="买点区间"):
            await agent_plan_ops.create_plan(
                AsyncMock(),
                _AK,
                plan_date=_PLAN_DATE,
                stock_code="600000",
                plan_type="buy",
                strategy="s",
                stop_loss=9.5,
                position_pct=10,
                basis="b",
            )

    @pytest.mark.asyncio
    async def test_sell_requires_target_price(self) -> None:
        with pytest.raises(BadRequestError, match="止盈"):
            await agent_plan_ops.create_plan(
                AsyncMock(),
                _AK,
                plan_date=_PLAN_DATE,
                stock_code="600000",
                plan_type="sell",
                strategy="s",
                stop_loss=9.5,
                position_pct=10,
                basis="b",
            )

    @pytest.mark.asyncio
    async def test_rejects_code_not_in_master(self) -> None:
        session = _session_with_scalars([None])
        with pytest.raises(NotFoundError, match="主数据"):
            await agent_plan_ops.create_plan(
                session,
                _AK,
                plan_date=_PLAN_DATE,
                stock_code="999999",
                plan_type="sell",
                strategy="s",
                stop_loss=9.5,
                position_pct=10,
                basis="b",
                target_price=11.0,
            )

    @pytest.mark.asyncio
    async def test_creates_new_plan(self) -> None:
        session = _session_with_scalars(["600000", None])
        plan = await agent_plan_ops.create_plan(
            session,
            _AK,
            plan_date=_PLAN_DATE,
            stock_code="600000",
            plan_type="buy",
            strategy="回踩接回",
            stop_loss=9.5,
            position_pct=10,
            basis="依据",
            buy_zone_low=9.9,
            buy_zone_high=10.2,
        )
        assert plan.status == "active"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_revives_expired_plan(self) -> None:
        existing = _plan_row("expired")
        session = _session_with_scalars(["600000", existing])
        plan = await agent_plan_ops.create_plan(
            session,
            _AK,
            plan_date=_PLAN_DATE,
            stock_code="600000",
            plan_type="sell",
            strategy="止盈离场",
            stop_loss=9.5,
            position_pct=10,
            basis="依据",
            target_price=11.0,
        )
        assert plan is existing
        assert plan.status == "active"
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_cancelled_plan(self) -> None:
        session = _session_with_scalars(["600000", _plan_row("cancelled")])
        with pytest.raises(BadRequestError, match="cancelled"):
            await agent_plan_ops.create_plan(
                session,
                _AK,
                plan_date=_PLAN_DATE,
                stock_code="600000",
                plan_type="sell",
                strategy="s",
                stop_loss=9.5,
                position_pct=10,
                basis="b",
                target_price=11.0,
            )

    @pytest.mark.asyncio
    async def test_rejects_triggered_plan(self) -> None:
        session = _session_with_scalars(["600000", _plan_row("triggered")])
        with pytest.raises(BadRequestError, match="triggered"):
            await agent_plan_ops.create_plan(
                session,
                _AK,
                plan_date=_PLAN_DATE,
                stock_code="600000",
                plan_type="sell",
                strategy="s",
                stop_loss=9.5,
                position_pct=10,
                basis="b",
                target_price=11.0,
            )


@pytest.mark.unit
class TestCancelPlan:
    @pytest.mark.asyncio
    async def test_missing_plan_404(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await agent_plan_ops.cancel_plan(session, _AK, plan_id=1)

    @pytest.mark.asyncio
    async def test_cancels_active_plan(self) -> None:
        session = AsyncMock()
        row = _plan_row("active")
        session.get = AsyncMock(return_value=row)
        plan = await agent_plan_ops.cancel_plan(session, _AK, plan_id=1)
        assert plan.status == "cancelled"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_triggered_plan_not_cancellable(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=_plan_row("triggered"))
        with pytest.raises(BadRequestError, match="不可取消"):
            await agent_plan_ops.cancel_plan(session, _AK, plan_id=1)

    @pytest.mark.asyncio
    async def test_cancelled_plan_idempotent(self) -> None:
        session = AsyncMock()
        row = _plan_row("cancelled")
        session.get = AsyncMock(return_value=row)
        plan = await agent_plan_ops.cancel_plan(session, _AK, plan_id=1)
        assert plan.status == "cancelled"
        session.commit.assert_not_awaited()


@pytest.mark.unit
class TestRemoveSelectionManual:
    @pytest.mark.asyncio
    async def test_missing_selection_404(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await agent_plan_ops.remove_selection_manual(session, _AK, selection_id=1)

    @pytest.mark.asyncio
    async def test_removed_row_idempotent(self) -> None:
        session = AsyncMock()
        row = MagicMock()
        row.status = "removed"
        row.agent_key = _AK
        session.get = AsyncMock(return_value=row)
        result = await agent_plan_ops.remove_selection_manual(session, _AK, selection_id=1)
        assert result.status == "removed"
        session.commit.assert_not_awaited()


def _orm_plan(stock_code: str = "600000") -> AgentTradePlan:
    return AgentTradePlan(
        id=11,
        agent_key=_AK,
        plan_date=_PLAN_DATE,
        stock_code=stock_code,
        plan_type="buy",
        strategy="回踩买点区间接回",
        buy_zone_low=Decimal("9.9000"),
        buy_zone_high=Decimal("10.2000"),
        target_price=None,
        stop_loss=Decimal("9.5000"),
        position_pct=Decimal("10.00"),
        status="active",
        selection_id=None,
        basis="依据",
        triggered_cl_ord_id=None,
    )


@pytest.mark.unit
class TestListPlanViews:
    @pytest.mark.asyncio
    async def test_fills_stock_name_from_master(self) -> None:

        session = AsyncMock()
        names_ret = MagicMock()
        names_ret.all.return_value = [("600000", "浦发银行")]
        session.execute = AsyncMock(return_value=names_ret)
        with patch.object(
            agent_plan_ops, "list_plans", AsyncMock(return_value=[_orm_plan()])
        ):
            views = await agent_plan_ops.list_plan_views(session, _AK, plan_date=_PLAN_DATE)
        assert len(views) == 1
        assert views[0].stock_code == "600000"
        assert views[0].stock_name == "浦发银行"
        assert views[0].plan_type == "buy"

    @pytest.mark.asyncio
    async def test_missing_master_code_yields_none_name(self) -> None:

        session = AsyncMock()
        names_ret = MagicMock()
        names_ret.all.return_value = []
        session.execute = AsyncMock(return_value=names_ret)
        with patch.object(
            agent_plan_ops, "list_plans", AsyncMock(return_value=[_orm_plan("999999")])
        ):
            views = await agent_plan_ops.list_plan_views(session, _AK, plan_date=_PLAN_DATE)
        assert views[0].stock_name is None

    @pytest.mark.asyncio
    async def test_no_plans_skips_name_query(self) -> None:

        session = AsyncMock()
        with patch.object(
            agent_plan_ops, "list_plans", AsyncMock(return_value=[])
        ):
            views = await agent_plan_ops.list_plan_views(session, _AK, plan_date=_PLAN_DATE)
        assert views == []
        session.execute.assert_not_awaited()
