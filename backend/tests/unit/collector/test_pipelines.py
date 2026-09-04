"""collector 数据管道（清洗/校验/去重步骤）契约测试。"""

import pytest

from collector.core.pipelines import DataPipeline, DeduplicateStep, NormalizeStep, ValidateStep


@pytest.mark.unit
class TestPipelineSteps:
    @pytest.mark.asyncio
    async def test_normalize_step(self) -> None:
        step = NormalizeStep()
        items = [{"a": "  hello  ", "b": "", "c": 1}]
        result = await step.run(items)
        assert result[0]["a"] == "hello"
        assert result[0]["b"] is None
        assert result[0]["c"] == 1

    @pytest.mark.asyncio
    async def test_validate_step(self) -> None:
        step = ValidateStep(required_fields=["a", "b"])
        items = [
            {"a": 1, "b": 2},
            {"a": 1, "b": None},
            {"a": None, "b": 2},
        ]
        result = await step.run(items)
        assert len(result) == 1
        assert result[0] == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_deduplicate_step(self) -> None:
        step = DeduplicateStep(key_fields=["code"])
        items = [{"code": "000001"}, {"code": "000002"}, {"code": "000001"}]
        result = await step.run(items)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_data_pipeline(self) -> None:
        pipeline = DataPipeline(
            steps=[
                NormalizeStep(),
                DeduplicateStep(key_fields=["code"]),
                ValidateStep(required_fields=["code"]),
            ]
        )
        items = [
            {"code": "000001 ", "value": 1},
            {"code": " 000001", "value": 2},
            {"code": "", "value": 3},
        ]
        result = await pipeline.process(items)
        assert len(result) == 1
        assert result[0]["code"] == "000001"
