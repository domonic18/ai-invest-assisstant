import json
import re
from pathlib import Path

from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    id: str
    name: str
    version: str
    model: str | None = None
    timeout: int = 300


class SkillDefinition(BaseModel):
    meta: SkillMeta
    description: str
    triggers: list[str]
    input_schema: dict
    output_schema: dict
    workflow: list[str]
    available_tools: list[str]
    examples: list[dict] = Field(default_factory=list)


class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: dict[str, SkillDefinition] = {}

    def load(self, skill_id: str) -> SkillDefinition:
        if skill_id in self._skills:
            return self._skills[skill_id]

        skill_path = self.skills_dir / skill_id / "SKILL.md"
        schema_path = self.skills_dir / skill_id / "schema.json"

        meta, sections = self._parse_markdown(skill_path.read_text())
        schema = json.loads(schema_path.read_text()) if schema_path.exists() else {}

        skill = SkillDefinition(
            meta=SkillMeta(**meta),
            description=sections.get("描述", ""),
            triggers=self._extract_list(sections.get("触发条件", "")),
            input_schema=schema.get("input", {}),
            output_schema=schema.get("output", {}),
            workflow=self._extract_list(sections.get("分析流程", "")),
            available_tools=self._extract_tools(sections.get("可用工具", "")),
            examples=self._extract_examples(sections.get("示例", "")),
        )
        self._skills[skill_id] = skill
        return skill

    def _parse_markdown(self, text: str):
        # Simple markdown parser for SKILL.md format
        lines = text.strip().split("\n")
        meta = {"id": "", "name": "", "version": "1.0.0"}
        sections = {}
        current_section = None
        current_content: list[str] = []

        for line in lines:
            if line.startswith("# "):
                meta["name"] = line[2:].strip()
            elif line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = line[3:].strip()
                current_content = []
            elif line.startswith("- **") and current_section == "元数据":
                # Parse metadata bullet
                match = re.match(r"- \*\*(\w+)\*\*:\s*(.+)", line)
                if match:
                    meta[match.group(1)] = match.group(2).strip()
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return meta, sections

    def _extract_list(self, text: str) -> list[str]:
        return [line.strip("- ").strip() for line in text.split("\n") if line.strip().startswith("-")]

    def _extract_tools(self, text: str) -> list[str]:
        return [line.strip("- ").strip() for line in text.split("\n") if line.strip().startswith("-")]

    def _extract_examples(self, text: str) -> list[dict]:
        return []
