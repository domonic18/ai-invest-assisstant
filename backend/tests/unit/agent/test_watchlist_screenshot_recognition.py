"""自选股截图识别执行器契约测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.skills import watchlist_screenshot_recognition as wsr
from app.agent.skills.watchlist_screenshot_recognition import (
    RecognizedStock,
    RecognizedStockList,
)


@pytest.mark.unit
class TestNormalizeCode:
    def test_strips_exchange_suffixes(self) -> None:
        assert wsr.normalize_code("SH600519") == "600519"
        assert wsr.normalize_code("sz.000001") == "000001"
        assert wsr.normalize_code("BJ:832000") == "832000"

    def test_extracts_six_digits_from_noise(self) -> None:
        assert wsr.normalize_code(" 贵州茅台 600519 ") == "600519"

    def test_returns_none_without_six_digits(self) -> None:
        assert wsr.normalize_code("60051") is None
        assert wsr.normalize_code("") is None


@pytest.mark.unit
class TestRunSkill:
    @pytest.mark.asyncio
    async def test_dedupes_normalizes_and_caps(self) -> None:
        rows = [
            RecognizedStock(code="SH600519", name="贵州茅台", confidence=0.9),
            RecognizedStock(code="600519", name="重复", confidence=0.8),
            RecognizedStock(code="abc", name="无代码", confidence=0.7),
            RecognizedStock(code="sz000001", name="平安银行", confidence=0.6),
        ] + [
            RecognizedStock(code=f"{700000 + i:06d}", name=f"填充{i}", confidence=0.5)
            for i in range(wsr._MAX_RECOGNIZED)
        ]
        structured = AsyncMock(
            return_value=RecognizedStockList(stocks=rows)
        )
        with (
            patch.object(wsr, "run_structured", structured),
            patch.object(
                wsr.PromptLoader,
                "load",
                return_value=SimpleNamespace(user_prompt_template="识别这张图"),
            ),
        ):
            result = await wsr.run_skill(
                object(), data=b"img", media_type="image/png"
            )

        assert structured.await_count == 1
        assert structured.await_args.kwargs["images"] == [(b"img", "image/png")]
        codes = [item.code for item in result]
        assert len(codes) == wsr._MAX_RECOGNIZED
        assert "600519" in codes
        assert "000001" in codes
        assert len(set(codes)) == len(codes)
