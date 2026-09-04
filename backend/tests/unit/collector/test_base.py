"""BaseCollector 基类契约测试（run 流程：采集→转换→校验→计数）。"""

import pytest

from collector.core.base import BaseCollector, CollectResult, CollectStatus


class DummyCollector(BaseCollector):
    """测试用采集器。"""

    def __init__(self, config: dict, fail_collect: bool = False):
        super().__init__(config)
        self.fail_collect = fail_collect

    async def collect(self, **kwargs) -> list[dict]:
        if self.fail_collect:
            raise ValueError("collect error")
        return [
            {"code": "000001", "value": 10},
            {"code": "000002", "value": 20},
            {"code": "", "value": 30},  # 无效项，由 validate 过滤
        ]

    async def transform(self, raw: dict) -> dict:
        return {"stock_code": raw["code"], "close": raw["value"]}

    async def validate(self, item: dict) -> bool:
        return bool(item.get("stock_code"))


@pytest.mark.unit
class TestBaseCollector:
    def test_result_default_values(self) -> None:
        result = CollectResult(source="test", data_type="dummy", status=CollectStatus.SUCCESS)
        assert result.items_collected == 0
        assert result.items_stored == 0
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        collector = DummyCollector({"source": "test", "data_type": "dummy"})
        result = await collector.run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_collected == 3
        assert result.items_stored == 2

    @pytest.mark.asyncio
    async def test_run_failed(self) -> None:
        collector = DummyCollector({"source": "test", "data_type": "dummy"}, fail_collect=True)
        result = await collector.run()

        assert result.status == CollectStatus.FAILED
        assert result.items_collected == 0
        assert result.items_stored == 0
        assert len(result.errors) == 1
        assert "collect error" in result.errors[0]
