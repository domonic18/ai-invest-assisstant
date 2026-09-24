"""自定义技能压缩包解析服务单元测试。"""

import io
import zipfile

import pytest

from app.services.skill.archive_analyzer import (
    ArchiveAnalyzeError,
    analyze_archive,
)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


_SKILL_MD = """---
name: 龙头战法复盘
description: 聚焦当日龙头股的战法复盘
allowed-tools: read_file, web_search
---

# 龙头战法复盘

## 目标
复盘当日龙头。
"""


@pytest.mark.unit
class TestAnalyzeArchive:
    def test_happy_path_root_level(self) -> None:
        suggestion = analyze_archive(_zip_bytes({"SKILL.md": _SKILL_MD}))

        assert suggestion.skill_id.startswith("skill") or suggestion.skill_id == "my-skill"
        assert suggestion.label == "龙头战法复盘"
        assert suggestion.description == "聚焦当日龙头股的战法复盘"
        assert suggestion.allowed_tools == ["read_file", "web_search"]
        assert "复盘当日龙头" in suggestion.system_prompt
        assert any(f["path"] == "SKILL.md" for f in suggestion.file_index)

    def test_happy_path_nested_root(self) -> None:
        suggestion = analyze_archive(
            _zip_bytes({"my-skill/SKILL.md": _SKILL_MD, "my-skill/README.md": "# hi"})
        )

        assert suggestion.skill_id == "my-skill"
        assert any(f["path"] == "my-skill/README.md" for f in suggestion.file_index)

    def test_non_zip_rejected(self) -> None:
        with pytest.raises(ArchiveAnalyzeError, match="无法识别"):
            analyze_archive(b"not a zip at all")

    def test_missing_skill_md_rejected(self) -> None:
        with pytest.raises(ArchiveAnalyzeError, match="未找到 SKILL.md"):
            analyze_archive(_zip_bytes({"README.md": "# hi"}))

    def test_zip_slip_rejected(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../evil/SKILL.md", _SKILL_MD)
        with pytest.raises(ArchiveAnalyzeError, match="不安全的压缩包路径"):
            analyze_archive(buf.getvalue())

    def test_sensitive_file_rejected(self) -> None:
        with pytest.raises(ArchiveAnalyzeError, match="敏感配置文件"):
            analyze_archive(
                _zip_bytes({"SKILL.md": _SKILL_MD, "skills/.env": "API_KEY=x"})
            )

    def test_secret_rejected(self) -> None:
        secret_md = _SKILL_MD + "\napi_key = \"sk-abcdefghij1234567890abcd\"\n"
        with pytest.raises(ArchiveAnalyzeError, match="疑似敏感信息"):
            analyze_archive(_zip_bytes({"SKILL.md": secret_md}))

    def test_placeholder_secret_allowed(self) -> None:
        placeholder_md = _SKILL_MD + '\napi_key = "<your-key-here>"\n'
        suggestion = analyze_archive(_zip_bytes({"SKILL.md": placeholder_md}))
        assert suggestion.label == "龙头战法复盘"

    def test_empty_zip_rejected(self) -> None:
        # 空 zip 的 EOCD 头（PK\x05\x06）不满足数据 magic bytes，被格式校验拒绝
        with pytest.raises(ArchiveAnalyzeError, match="无法识别"):
            analyze_archive(_zip_bytes({}))

    def test_zip_only_dirs_rejected(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("only-dir/", "")
        with pytest.raises(ArchiveAnalyzeError, match="为空"):
            analyze_archive(buf.getvalue())
