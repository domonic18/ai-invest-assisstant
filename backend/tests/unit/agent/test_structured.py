"""run_structured 单轮结构化调用契约测试。"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime.structured import run_structured


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
            "app.agent.runtime.structured.resolve_default_llm",
            new=AsyncMock(return_value=SimpleNamespace(protocol=protocol)),
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
