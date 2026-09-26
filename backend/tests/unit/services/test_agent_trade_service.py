"""交易 Agent 下单出口测试（execute_agent_order 链路 mock：账户解析→风控→柜台→落库）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.services.trading import account_service
from app.services.trading.agent_trade_service import (
    RiskRejectedError,
    cancel_agent_order,
    ensure_agent_account,
    execute_agent_order,
)
from app.services.trading.errors import AgentAccountNotDesignatedError
from app.services.trading.risk_control import RiskCheckResult

_COUNTER_RAW = [
    {
        "cl_ord_id": "CL-1",
        "symbol": "SHSE.600000",
        "side": 1,
        "order_type": 1,
        "price": 10.5,
        "volume": 100,
        "status": 1,
        "created_at": "2026-09-25 09:31:00",
    }
]


def _session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    return session


def _agent_account(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": 5,
        "name": "agent 专属",
        "agent_key": "short-line",
        "is_enabled": True,
        "token_encrypted": "cipher",
        "counter_account_id": "acc-1",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _agent() -> SimpleNamespace:
    """注册行替身（风控阈值读 risk_max_*，账户解析读 agent_key）。"""
    return SimpleNamespace(
        agent_key="short-line",
        risk_max_position_pct=20,
        risk_max_total_pct=80,
        risk_max_daily_orders=10,
    )


def _patch_chain(account: SimpleNamespace | None, risk_passed: bool = True):
    """打桩整条外部依赖链（账户解析/配置/主数据/风控/柜台），返回 (patches, mocks)。"""
    client = MagicMock()
    client.place_order = AsyncMock(return_value=_COUNTER_RAW)
    client.cancel_order = AsyncMock(return_value={"ok": True})
    patches = [
        patch.object(
            account_service, "resolve_agent_account", AsyncMock(return_value=account)
        ),
        patch.object(account_service, "credentials_for", lambda _a: SimpleNamespace()),
        patch(
            "app.services.trading.agent_trade_service.resolve_counter_symbol",
            AsyncMock(return_value="SHSE.600000"),
        ),
        patch(
            "app.services.trading.agent_trade_service.check_order_risk",
            AsyncMock(return_value=RiskCheckResult(passed=risk_passed, reasons=["单票市值超上限"] if not risk_passed else [])),
        ),
        patch(
            "app.services.trading.agent_trade_service.get_client",
            lambda: client,
        ),
    ]
    upsert_mock = AsyncMock()
    patches.append(
        patch("app.services.trading.agent_trade_service._upsert_orders", upsert_mock)
    )
    return patches, client, upsert_mock


@pytest.mark.unit
class TestExecuteAgentOrder:
    @pytest.mark.asyncio
    async def test_happy_path_places_order_and_upserts_local_row(self) -> None:
        session = _session()
        patches, client, upsert_mock = _patch_chain(_agent_account())
        for p in patches:
            p.start()
        try:
            result = await execute_agent_order(
                session, _agent(), symbol="600000", side="buy", volume=100, price=10.5
            )
        finally:
            for p in patches:
                p.stop()

        assert result["cl_ord_id"] == "CL-1"
        assert result["risk"].passed
        client.place_order.assert_awaited_once()
        args = client.place_order.await_args.args
        assert args[1] == "SHSE.600000"  # 柜台完整代码
        assert args[2] == "buy"
        assert args[3] == 100
        # 轻量落库：本地委托行带 agent 标记，供盘中日笔数风控计数
        upsert_mock.assert_awaited_once()
        assert upsert_mock.await_args.kwargs["rows"][0]["order_source"] == "agent"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_risk_rejected_raises_and_never_hits_counter(self) -> None:
        session = _session()
        patches, client, upsert_mock = _patch_chain(
            _agent_account(), risk_passed=False
        )
        for p in patches:
            p.start()
        try:
            with pytest.raises(RiskRejectedError, match="单票市值超上限"):
                await execute_agent_order(
                    session, _agent(), symbol="600000", side="buy", volume=100, price=10.5
                )
        finally:
            for p in patches:
                p.stop()
        client.place_order.assert_not_awaited()
        upsert_mock.assert_not_awaited()
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_designated_account_propagates(self) -> None:
        session = _session()
        patches, client, _ = _patch_chain(None)
        patches[0] = patch(
            "app.services.trading.agent_trade_service.account_service.resolve_agent_account",
            AsyncMock(side_effect=AgentAccountNotDesignatedError()),
        )
        for p in patches:
            p.start()
        try:
            with pytest.raises(AgentAccountNotDesignatedError):
                await execute_agent_order(
                    session, _agent(), symbol="600000", side="buy", volume=100
                )
        finally:
            for p in patches:
                p.stop()
        client.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_agent_account_rejected(self) -> None:
        session = _session()
        patches, client, _ = _patch_chain(_agent_account(agent_key=None))
        for p in patches:
            p.start()
        try:
            with pytest.raises(BadRequestError, match="不是该 Agent 的专属账户"):
                await execute_agent_order(
                    session, _agent(), symbol="600000", side="buy", volume=100
                )
        finally:
            for p in patches:
                p.stop()
        client.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disabled_account_rejected(self) -> None:
        session = _session()
        patches, client, _ = _patch_chain(_agent_account(is_enabled=False))
        for p in patches:
            p.start()
        try:
            with pytest.raises(BadRequestError, match="停用"):
                await execute_agent_order(
                    session, _agent(), symbol="600000", side="buy", volume=100
                )
        finally:
            for p in patches:
                p.stop()
        client.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_side_and_volume(self) -> None:
        session = _session()
        patches, client, _ = _patch_chain(_agent_account())
        for p in patches:
            p.start()
        try:
            with pytest.raises(BadRequestError, match="side"):
                await execute_agent_order(
                    session, _agent(), symbol="600000", side="hold", volume=100
                )
            with pytest.raises(BadRequestError, match="正数"):
                await execute_agent_order(session, _agent(), symbol="600000", side="buy", volume=0)
        finally:
            for p in patches:
                p.stop()
        client.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_counter_rejected_status_still_returns_row(self) -> None:
        """柜台受理后拒单（status=8）不是异常：原文透传给工具层转述。"""
        session = _session()
        patches, client, _ = _patch_chain(_agent_account())
        client.place_order = AsyncMock(
            return_value=[
                {**_COUNTER_RAW[0], "status": 8, "ord_rej_reason_detail": "资金不足"}
            ]
        )
        for p in patches:
            p.start()
        try:
            result = await execute_agent_order(
                session, _agent(), symbol="600000", side="buy", volume=100, price=10.5
            )
        finally:
            for p in patches:
                p.stop()
        assert result["status"] == 8
        assert result["ord_rej_reason_detail"] == "资金不足"


@pytest.mark.unit
class TestHelpers:
    @pytest.mark.asyncio
    async def test_cancel_agent_order_delegates_to_client(self) -> None:
        account = _agent_account()
        client = MagicMock()
        client.cancel_order = AsyncMock(return_value={"ok": True})
        with (
            patch.object(
                account_service, "credentials_for", lambda _a: SimpleNamespace()
            ),
            patch(
                "app.services.trading.agent_trade_service.get_client", lambda: client
            ),
        ):
            await cancel_agent_order(account, "CL-1")  # type: ignore[arg-type]
        client.cancel_order.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_agent_account_disabled_raises(self) -> None:
        session = _session()
        with patch.object(
            account_service,
            "resolve_agent_account",
            AsyncMock(return_value=_agent_account(is_enabled=False)),
        ):
            with pytest.raises(BadRequestError, match="停用"):
                await ensure_agent_account(session, "short-line")

    @pytest.mark.asyncio
    async def test_ensure_agent_account_ok(self) -> None:
        session = _session()
        account = _agent_account()
        with patch.object(
            account_service, "resolve_agent_account", AsyncMock(return_value=account)
        ):
            assert await ensure_agent_account(session, "short-line") is account
