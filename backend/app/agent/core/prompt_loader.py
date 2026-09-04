"""Agent Prompt YAML 配置的加载与缓存。"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PromptSection(BaseModel):
    """结构化输出的一个内容分区（key 为输出键，title 为展示名）。"""

    key: str
    title: str
    requirements: str = ""


class PromptConfig(BaseModel):
    id: str
    name: str
    version: str
    model: str | None = None
    description: str = ""
    system_prompt: str
    user_prompt_template: str = ""
    output_schema: dict = Field(default_factory=dict)
    sections: list[PromptSection] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)


class PromptLoader:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir
        self._cache: dict[str, PromptConfig] = {}

    def load(self, scope: str, prompt_id: str) -> PromptConfig:
        key = f"{scope}/{prompt_id}"
        if key in self._cache:
            return self._cache[key]

        path = self.prompts_dir / scope / f"{prompt_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = PromptConfig(**data)
        self._cache[key] = config
        return config

    def reload(self, scope: str, prompt_id: str):
        key = f"{scope}/{prompt_id}"
        self._cache.pop(key, None)
        return self.load(scope, prompt_id)
