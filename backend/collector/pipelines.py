"""Data cleaning pipeline for collectors."""

from abc import ABC, abstractmethod
from typing import Any


class PipelineStep(ABC):
    """数据清洗管道步骤基类。"""

    @abstractmethod
    async def run(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """处理数据并返回处理后的列表。"""


class DeduplicateStep(PipelineStep):
    """基于组合键去重。"""

    def __init__(self, key_fields: list[str] | None = None):
        self.key_fields = key_fields or []

    async def run(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.key_fields:
            return items

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            key = "_".join(str(item.get(field, "")) for field in self.key_fields)
            if key and key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique


class NormalizeStep(PipelineStep):
    """字段标准化：去除字符串首尾空格、空字符串转 None。"""

    async def run(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            cleaned: dict[str, Any] = {}
            for key, value in item.items():
                if isinstance(value, str):
                    value = value.strip()
                    if value == "":
                        value = None
                cleaned[key] = value
            normalized.append(cleaned)
        return normalized


class ValidateStep(PipelineStep):
    """必填字段校验。"""

    def __init__(self, required_fields: list[str] | None = None):
        self.required_fields = required_fields or []

    async def run(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid: list[dict[str, Any]] = []
        for item in items:
            if all(item.get(field) is not None for field in self.required_fields):
                valid.append(item)
        return valid


class DataPipeline:
    """数据清洗管道 — 组合多个步骤顺序执行。"""

    def __init__(self, steps: list[PipelineStep] | None = None):
        self.steps = steps or [
            NormalizeStep(),
            ValidateStep(),
        ]

    async def process(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for step in self.steps:
            items = await step.run(items)
        return items
