"""run_structured 单轮结构化调用契约测试（含额度耗尽主备切换重试）。"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime.structured import run_structured


def _rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return openai.RateLimitError(
        "quota exceeded",
        response=httpx.Response(status_code=429, request=request),
        body=None,
    )


class _Out(BaseModel):
    value: str


def _validation_error() -> ValidationError:
    """构造真实 pydantic ValidationError（模拟 schema 校验失败）。"""
    try:
        _Out.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("unreachable")


class _FakeStructured:
    """模拟 with_structured_output 返回的 runnable：按序弹出预置结果。"""

    def __init__(self, results: list[Any]) -> None:
        self._results = results
        self.prompts: list[Any] = []

    async def ainvoke(self, messages: list[Any]) -> Any:
        self.prompts.append(messages[0].content)
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _FakeModel:
    def __init__(self, structured: _FakeStructured) -> None:
        self._structured = structured
        self.methods: list[str | None] = []

    def with_structured_output(
        self, _schema: type[BaseModel], method: str | None = None
    ) -> _FakeStructured:
        self.methods.append(method)
        return self._structured


def _patch_run_env(structured: _FakeStructured, *, protocol: str = "anthropic"):
    fake_model = _FakeModel(structured)
    return (
        patch(
            "app.agent.runtime.structured.resolve_llm",
            new=AsyncMock(return_value=(SimpleNamespace(protocol=protocol), "system")),
        ),
        patch(
            "app.agent.runtime.structured.build_langchain_model",
            return_value=fake_model,
        ),
        fake_model,
    )


@pytest.mark.unit
class TestRunStructured:
    @pytest.mark.asyncio
    async def test_success_text_only(self) -> None:
        structured = _FakeStructured([_Out(value="ok")])
        patches = _patch_run_env(structured)
        with patches[0], patches[1]:
            result = await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
            )

        assert result == _Out(value="ok")
        assert structured.prompts == ["hello"]

    @pytest.mark.asyncio
    async def test_success_with_images(self) -> None:
        structured = _FakeStructured([_Out(value="ok")])
        patches = _patch_run_env(structured)
        with patches[0], patches[1]:
            result = await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="看图",
                images=[(b"img-bytes", "image/png")],
            )

        assert result == _Out(value="ok")
        content = structured.prompts[0]
        assert content[0] == {"type": "text", "text": "看图"}
        image_block = content[1]
        assert image_block["type"] == "image_url"
        url = image_block["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_retries_once_on_validation_error(self) -> None:
        structured = _FakeStructured([_validation_error(), _Out(value="ok")])
        patches = _patch_run_env(structured)
        with patches[0], patches[1]:
            result = await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
            )

        assert result == _Out(value="ok")
        assert len(structured.prompts) == 2

    @pytest.mark.asyncio
    async def test_raises_after_retry_exhausted(self) -> None:
        structured = _FakeStructured([_validation_error(), _validation_error()])
        patches = _patch_run_env(structured)
        with patches[0], patches[1], pytest.raises(ValidationError):
            await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
            )

        assert len(structured.prompts) == 2

    @pytest.mark.asyncio
    async def test_anthropic_provider_uses_json_schema(self) -> None:
        structured = _FakeStructured([_Out(value="ok")])
        p_llm, p_model, fake_model = _patch_run_env(structured, protocol="anthropic")
        with p_llm, p_model:
            await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
            )

        assert fake_model.methods == ["json_schema"]

    @pytest.mark.asyncio
    async def test_openai_provider_uses_function_calling(self) -> None:
        structured = _FakeStructured([_Out(value="ok")])
        p_llm, p_model, fake_model = _patch_run_env(structured, protocol="openai")
        with p_llm, p_model:
            await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
            )

        assert fake_model.methods == ["function_calling"]

    @pytest.mark.asyncio
    async def test_retries_on_output_parsing_exception(self) -> None:
        structured = _FakeStructured(
            [OutputParserException("bad json"), _Out(value="ok")]
        )
        patches = _patch_run_env(structured)
        with patches[0], patches[1]:
            result = await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
            )

        assert result == _Out(value="ok")
        assert len(structured.prompts) == 2

    @pytest.mark.asyncio
    async def test_config_id_bypasses_resolve_llm(self) -> None:
        """config_id 显式指定条目：不查 resolve_llm 分流，按该条目建模型。"""
        structured = _FakeStructured([_Out(value="ok")])
        fake_model = _FakeModel(structured)
        p_by_id = patch(
            "app.agent.runtime.structured.resolve_llm_by_id",
            new=AsyncMock(
                return_value=SimpleNamespace(protocol="openai", model_name="m2.5")
            ),
        )
        p_model = patch(
            "app.agent.runtime.structured.build_langchain_model",
            return_value=fake_model,
        )
        session = cast(AsyncSession, object())
        with p_by_id, p_model:
            result = await run_structured(
                session,
                result_type=_Out,
                user_prompt="hello",
                config_id=7,
            )

        assert result == _Out(value="ok")
        assert fake_model.methods == ["function_calling"]

    @pytest.mark.asyncio
    async def test_failover_retries_with_backup_on_rate_limit(self) -> None:
        """额度耗尽：主配置进冷却，重解析切备用（含协议 method 重选）当次重试。"""
        primary = SimpleNamespace(config_id=1, protocol="openai", model_name="m1")
        backup = SimpleNamespace(config_id=2, protocol="anthropic", model_name="m2")
        structured = _FakeStructured([_rate_limit_error(), _Out(value="ok")])
        fake_model = _FakeModel(structured)
        built: list[Any] = []

        def _fake_build(cfg: Any, **_kw: Any) -> _FakeModel:
            built.append(cfg)
            return fake_model

        with (
            patch(
                "app.agent.runtime.structured.resolve_llm_by_id",
                new=AsyncMock(side_effect=[primary, backup]),
            ),
            patch(
                "app.agent.runtime.structured.build_langchain_model",
                side_effect=_fake_build,
            ),
            patch(
                "app.agent.runtime.structured.mark_unhealthy", new=AsyncMock()
            ) as p_mark,
        ):
            result = await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
                config_id=1,
            )

        assert result == _Out(value="ok")
        assert [cfg.config_id for cfg in built] == [1, 2]
        # method 按备用协议重选：主 openai function_calling → 备用 anthropic json_schema
        assert fake_model.methods == ["function_calling", "json_schema"]
        p_mark.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_failover_raises_when_no_backup_switch(self) -> None:
        """无备用可切（门返回同一条目）时原样上抛，不对同一死模型重复调用。"""
        primary = SimpleNamespace(config_id=1, protocol="openai", model_name="m1")
        structured = _FakeStructured([_rate_limit_error()])
        fake_model = _FakeModel(structured)
        with (
            patch(
                "app.agent.runtime.structured.resolve_llm_by_id",
                new=AsyncMock(return_value=primary),
            ),
            patch(
                "app.agent.runtime.structured.build_langchain_model",
                return_value=fake_model,
            ),
            patch("app.agent.runtime.structured.mark_unhealthy", new=AsyncMock()),
            pytest.raises(openai.RateLimitError),
        ):
            await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
                config_id=1,
            )

        assert len(structured.prompts) == 1

    @pytest.mark.asyncio
    async def test_non_classified_error_propagates_without_retry(self) -> None:
        """非额度类异常（如 5xx/程序错误）不触发主备重试。"""
        structured = _FakeStructured([RuntimeError("connection reset")])
        fake_model = _FakeModel(structured)
        with (
            patch(
                "app.agent.runtime.structured.resolve_llm_by_id",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        config_id=1, protocol="openai", model_name="m1"
                    )
                ),
            ),
            patch(
                "app.agent.runtime.structured.build_langchain_model",
                return_value=fake_model,
            ),
            patch(
                "app.agent.runtime.structured.mark_unhealthy", new=AsyncMock()
            ) as p_mark,
            pytest.raises(RuntimeError),
        ):
            await run_structured(
                cast(AsyncSession, object()),
                result_type=_Out,
                user_prompt="hello",
                config_id=1,
            )

        assert len(structured.prompts) == 1
        p_mark.assert_not_awaited()
