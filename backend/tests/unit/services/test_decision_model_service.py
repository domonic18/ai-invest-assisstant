"""判断模型服务测试：配置解析（健康门/extra 覆盖）、failover 编排、连通性探测。"""

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import Base
from app.core.decision_model import (
    DEFAULT_THRESHOLDS,
    DecisionModelConfigError,
    DecisionModelRequestError,
    DecisionModelUnavailableError,
    JudgeNoulAnswer,
    JudgeResponse,
    JudgeUsage,
)
from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.services.admin import decision_model_service as dms
from app.services.admin.decision_model_service import (
    ask_decision,
    build_decision_client,
    resolve_decision_llm,
)
from app.services.admin.llm_config_service import (
    LLMConfigNotConfiguredError,
    LLMConfigService,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "a-32-byte-secret-key-for-tests!")


@pytest.fixture(autouse=True)
def _hermetic_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """隔离 redis：健康门/冷却查询打桩（本地 redis 常驻时连接池跨 loop 复用会炸）。"""
    monkeypatch.setattr(
        "app.services.admin.llm_failover.is_unhealthy",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.admin.llm_config_service.degraded_until",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.admin.llm_config_service.clear_unhealthy",
        AsyncMock(),
    )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[LLMConfig.__table__])
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as db:
        yield db
    await engine.dispose()


async def _create_decision(session: Any, name: str = "Jev", **kw: Any):
    return await LLMConfigService(session).create_config(
        LLMConfigCreate(
            name=name,
            provider="openrouter",
            base_url="https://openrouter.ai/api",
            api_key=f"sk-or-{name}",
            model_name="jev-latest",
            purpose="decision",
            **kw,
        )
    )


def _judge_response(config_id: int | None = None) -> JudgeResponse:
    return JudgeResponse(
        model="typesafe/jev-1.13-20260917",
        answers={"q": JudgeNoulAnswer(type="noul", noul=0.42)},
        usage=JudgeUsage(input_tokens=10, output_tokens=2, cost=0.001),
        request_id="gen-dec-test",
        latency_ms=88,
        config_id=config_id,
    )


class _StubClient:
    """ask_decision 的桩：按构造时的 outcome 抛错或返回。"""

    def __init__(self, outcome: tuple[str, Any]) -> None:
        self.outcome = outcome
        self.calls = 0

    async def ask(self, state: Any, questions: Any) -> JudgeResponse:
        self.calls += 1
        kind, value = self.outcome
        if kind == "raise":
            raise value
        return value


class TestResolveDecisionLLM:
    async def test_raises_when_missing(self, session: Any) -> None:
        with pytest.raises(LLMConfigNotConfiguredError):
            await resolve_decision_llm(session)

    async def test_create_forces_systemone_protocol(self, session: Any) -> None:
        created = await _create_decision(session, name="误选协议", protocol="openai")
        assert created.protocol == "systemone"

        updated = await LLMConfigService(session).update_config(
            created.id, LLMConfigUpdate(protocol="anthropic")
        )
        assert updated.protocol == "systemone"

    async def test_resolve_decrypts_and_applies_extra(self, session: Any) -> None:
        created = await _create_decision(
            session,
            extra={"timeout_seconds": 3.5, "thresholds": {"observe": 0.5, "fund_action": 0.9}},
        )
        resolved = await resolve_decision_llm(session)
        assert resolved.config_id == created.id
        assert resolved.model_name == "jev-latest"
        assert resolved.api_key == "sk-or-Jev"
        assert resolved.timeout_seconds == 3.5
        assert resolved.thresholds.observe == 0.5
        assert resolved.thresholds.fund_action == 0.9

    async def test_resolve_defaults_without_extra(self, session: Any) -> None:
        await _create_decision(session)
        resolved = await resolve_decision_llm(session)
        assert resolved.thresholds == DEFAULT_THRESHOLDS
        assert resolved.timeout_seconds == get_settings().decision_model_timeout_seconds

    async def test_resolve_invalid_extra_raises(self, session: Any) -> None:
        await _create_decision(
            session, extra={"thresholds": {"observe": 0.9, "fund_action": 0.5}}
        )
        with pytest.raises(DecisionModelConfigError):
            await resolve_decision_llm(session)

    async def test_resolve_switches_to_backup_when_unhealthy(self, session: Any) -> None:
        primary = await _create_decision(session, name="主")
        backup = await _create_decision(session, name="备")
        await LLMConfigService(session).update_config(
            primary.id, LLMConfigUpdate(backup_config_id=backup.id)
        )
        with patch(
            "app.services.admin.llm_failover.is_unhealthy",
            new=AsyncMock(return_value=True),
        ):
            resolved = await resolve_decision_llm(session)
        assert resolved.config_id == backup.id

    async def test_build_client_carries_thresholds(self, session: Any) -> None:
        created = await _create_decision(
            session, extra={"thresholds": {"observe": 0.5, "fund_action": 0.9}}
        )
        resolved = await resolve_decision_llm(session)
        client = build_decision_client(resolved)
        assert client.thresholds.fund_action == 0.9
        assert client.config_id == created.id


class TestAskDecision:
    async def test_success(self, session: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        created = await _create_decision(session)
        expected = _judge_response(created.id)
        monkeypatch.setattr(
            dms, "build_decision_client", lambda cfg: _StubClient(("ok", expected))
        )
        assert await ask_decision(session, state={}, questions={}) == expected

    async def test_unavailable_failover_to_backup_once(
        self, session: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        primary = await _create_decision(session, name="主")
        backup = await _create_decision(session, name="备")
        await LLMConfigService(session).update_config(
            primary.id, LLMConfigUpdate(backup_config_id=backup.id)
        )
        expected = _judge_response(backup.id)
        built: list[int] = []

        def fake_build(cfg: Any) -> _StubClient:
            built.append(cfg.config_id)
            if cfg.config_id == primary.id:
                return _StubClient(("raise", DecisionModelUnavailableError("402 exhausted")))
            return _StubClient(("ok", expected))

        monkeypatch.setattr(dms, "build_decision_client", fake_build)
        mark_mock = AsyncMock()
        monkeypatch.setattr(dms, "mark_unhealthy", mark_mock)
        # 第一次解析：主健康；标记冷却后重解析：主不健康 → 切备用
        monkeypatch.setattr(
            "app.services.admin.llm_failover.is_unhealthy",
            AsyncMock(side_effect=[False, True]),
        )

        result = await ask_decision(session, state={}, questions={})

        assert result == expected
        assert built == [primary.id, backup.id]
        assert mark_mock.await_count == 1
        assert mark_mock.await_args.args[0] == primary.id

    async def test_unavailable_without_backup_reraises(
        self, session: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        primary = await _create_decision(session, name="唯一")
        built: list[int] = []

        def fake_build(cfg: Any) -> _StubClient:
            built.append(cfg.config_id)
            return _StubClient(("raise", DecisionModelUnavailableError("429 limited")))

        monkeypatch.setattr(dms, "build_decision_client", fake_build)
        mark_mock = AsyncMock()
        monkeypatch.setattr(dms, "mark_unhealthy", mark_mock)
        monkeypatch.setattr(
            "app.services.admin.llm_failover.is_unhealthy",
            AsyncMock(side_effect=[False, True]),
        )

        with pytest.raises(DecisionModelUnavailableError, match="429"):
            await ask_decision(session, state={}, questions={})

        assert built == [primary.id]  # 重解析同配置 → 上抛，不再重建客户端重试
        assert mark_mock.await_count == 1

    async def test_request_error_does_not_switch(
        self, session: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """认证/pin 类错误重试与切备无意义——原样上抛且不标记冷却。"""
        primary = await _create_decision(session, name="主")
        backup = await _create_decision(session, name="备")
        await LLMConfigService(session).update_config(
            primary.id, LLMConfigUpdate(backup_config_id=backup.id)
        )
        built: list[int] = []

        def fake_build(cfg: Any) -> _StubClient:
            built.append(cfg.config_id)
            return _StubClient(("raise", DecisionModelRequestError("401 invalid key")))

        monkeypatch.setattr(dms, "build_decision_client", fake_build)
        mark_mock = AsyncMock()
        monkeypatch.setattr(dms, "mark_unhealthy", mark_mock)
        monkeypatch.setattr(
            "app.services.admin.llm_failover.is_unhealthy",
            AsyncMock(side_effect=[False, True]),
        )

        with pytest.raises(DecisionModelRequestError, match="401"):
            await ask_decision(session, state={}, questions={})

        assert built == [primary.id]
        assert mark_mock.await_count == 0


def _stub_http(captured: dict[str, Any], *, status: int = 200, body: dict[str, Any] | None = None):
    """替换 httpx.AsyncClient 的桩：捕获请求并返回固定响应。"""

    class _StubClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "_StubClient":
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, url: str, headers: Any = None, json: Any = None) -> Any:
            captured["url"] = url
            captured["json"] = json
            return httpx.Response(status, json=body or {})

    return _StubClient


class TestConnectionProbe:
    async def test_decision_probe_hits_systemone_path(
        self, session: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """decision 条目「测试连接」走 systemone wire 最小 noul 探针（= 真实冒烟）。"""
        created = await _create_decision(session)
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "app.services.admin.llm_config_service.httpx.AsyncClient",
            _stub_http(
                captured,
                body={
                    "model": "typesafe/jev-1.13-20260917",
                    "answers": {"connected": {"type": "noul", "noul": 0.91}},
                    "usage": {"input_tokens": 12, "output_tokens": 4, "cost": 0.0001},
                },
            ),
        )

        result = await LLMConfigService(session).test_config_connection(created.id)

        assert result.status == "success"
        assert captured["url"] == "https://openrouter.ai/api/v1/systemone"
        question = captured["json"]["questions"]["connected"]
        assert question["type"] == "noul"
        assert set(question["criteria"]) == {"true", "false"}
        refreshed = await LLMConfigService(session).get_config(created.id)
        assert refreshed.last_test_status == "success"

    async def test_decision_probe_failure_records_error(
        self, session: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created = await _create_decision(session)
        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            "app.services.admin.llm_config_service.httpx.AsyncClient",
            _stub_http(
                captured,
                status=401,
                body={"error": {"message": "invalid api key", "code": 401}},
            ),
        )

        result = await LLMConfigService(session).test_config_connection(created.id)

        assert result.status == "failed"
        assert "401" in result.detail
        refreshed = await LLMConfigService(session).get_config(created.id)
        assert refreshed.last_test_status == "failed"
