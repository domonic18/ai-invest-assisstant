"""自定义技能压缩包解析：上传 zip/tar.gz → 解析 SKILL.md → 表单预填建议。

移植自 SquadSight ``app/services/skill/archive.py``（裁剪版）：本系统 custom
skill = 配置而非可执行目录，故不做归一化重打包/落盘，只产出建议字段
（skill_id/label/description/SKILL.md/allowed-tools + 文件索引）。

安全契约：magic bytes 校验、zip-slip 防护、敏感配置文件拦截、密钥扫描拒绝。
"""

import io
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import yaml

from app.core.config import get_settings
from app.schemas.skill import CustomSkillSection

# Frontmatter 解析正则（与 SquadSight 同款）
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

ZIP_MAGIC_BYTES = b"PK\x03\x04"
GZIP_MAGIC_BYTES = b"\x1f\x8b"


class ArchiveAnalyzeError(ValueError):
    """压缩包校验/解析失败（消息面向用户展示）。"""


@dataclass
class SkillArchiveSuggestion:
    """压缩包解析出的自定义技能预填建议。"""

    skill_id: str
    label: str
    description: str | None
    skill_md: str
    system_prompt: str
    user_prompt_template: str | None
    sections: list[CustomSkillSection] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    file_index: list[dict[str, Any]] = field(default_factory=list)


def analyze_archive(data: bytes) -> SkillArchiveSuggestion:
    """校验并解析压缩包，返回表单预填建议。

    Raises:
        ArchiveAnalyzeError: 格式/大小不合规、路径不安全、缺 SKILL.md、
            含敏感配置文件或疑似密钥。
    """
    settings = get_settings()
    max_size = settings.skill_upload_max_mb * 1024 * 1024
    if len(data) > max_size:
        raise ArchiveAnalyzeError(
            f"压缩包过大：超过上限 {settings.skill_upload_max_mb}MB"
        )

    files = _extract(data)
    skill_path, root_dir = _find_skill_md(files)
    skill_md_raw = files[skill_path].decode("utf-8", errors="replace")
    frontmatter, body_md = _parse_frontmatter(skill_md_raw)

    _reject_sensitive_files(files)
    _reject_secrets(files)

    name = str(frontmatter.get("name") or "").strip()
    label = name or root_dir or "自定义技能"
    skill_id = _suggest_skill_id(root_dir or name)
    description = str(frontmatter.get("description") or "").strip() or None
    allowed_tools = _normalize_tools(frontmatter.get("allowed-tools"))

    return SkillArchiveSuggestion(
        skill_id=skill_id,
        label=label,
        description=description,
        skill_md=skill_md_raw.strip() or body_md.strip(),
        system_prompt=body_md.strip(),
        user_prompt_template=None,
        sections=_sections_from_frontmatter(frontmatter),
        allowed_tools=allowed_tools,
        file_index=[
            {"path": path, "size": len(content)} for path, content in sorted(files.items())
        ],
    )


# ============================================================
# 解包与定位
# ============================================================


def _check_path(name: str) -> None:
    """zip-slip 防护：禁止绝对路径与 ``..`` 穿越。"""
    p = PurePosixPath(name)
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise ArchiveAnalyzeError(f"检测到不安全的压缩包路径: {name}")


_JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _is_junk(rel_path: str) -> bool:
    parts = PurePosixPath(rel_path).parts
    if any(part == "__MACOSX" for part in parts):
        return True
    name = parts[-1] if parts else ""
    return name.startswith("._") or name in _JUNK_NAMES


def _extract(data: bytes) -> dict[str, bytes]:
    """解包到 ``{rel_path: bytes}``（跳过目录与系统垃圾文件）。"""
    files: dict[str, bytes] = {}
    if data[:4] == ZIP_MAGIC_BYTES:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir() or _is_junk(info.filename):
                    continue
                _check_path(info.filename)
                files[info.filename] = zf.read(info)
    elif data[:2] == GZIP_MAGIC_BYTES:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile() or _is_junk(member.name):
                    continue
                _check_path(member.name)
                extracted = tf.extractfile(member)
                if extracted is not None:
                    files[member.name] = extracted.read()
    else:
        raise ArchiveAnalyzeError("无法识别的压缩包格式，仅支持 .zip / .tar.gz")

    if not files:
        raise ArchiveAnalyzeError("压缩包为空或仅含目录")
    return files


def _find_skill_md(files: dict[str, bytes]) -> tuple[str, str]:
    """定位 SKILL.md（路径最短优先），返回 ``(path, 根目录名)``。"""
    candidates = [p for p in files if PurePosixPath(p).name.lower() == "skill.md"]
    if not candidates:
        raise ArchiveAnalyzeError("压缩包内未找到 SKILL.md（技能包必须包含 SKILL.md）")
    skill_path = min(candidates, key=len)
    parts = PurePosixPath(skill_path).parts
    root_dir = parts[0] if len(parts) > 1 else ""
    return skill_path, root_dir


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """拆分 YAML frontmatter 与 Markdown 正文。"""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        meta = {}
    frontmatter = meta if isinstance(meta, dict) else {}
    return frontmatter, content[match.end():]


# ============================================================
# 建议字段合成
# ============================================================


def _suggest_skill_id(raw: str) -> str:
    """名称 → kebab-case skill_id 建议（与创建接口 pattern 对齐）。"""
    cleaned = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    return cleaned or "my-skill"


def _normalize_tools(raw: Any) -> list[str]:
    """frontmatter allowed-tools → list[str]（接受列表或逗号/空格分隔字符串）。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [item for item in re.split(r"[,\s]+", raw) if item]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _sections_from_frontmatter(frontmatter: dict[str, Any]) -> list[CustomSkillSection]:
    """frontmatter 的 sections 声明 → 结构化输出分区（容错，非法即忽略）。"""
    raw = frontmatter.get("sections")
    if not isinstance(raw, list):
        return []
    sections: list[CustomSkillSection] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        title = str(item.get("title") or "").strip()
        if key and title:
            sections.append(CustomSkillSection(key=key, title=title))
    return sections


# ============================================================
# 敏感文件与密钥扫描
# ============================================================

_SENSITIVE_FILES = {
    ".env",
    "credentials.json",
    "credentials",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".npmrc",
    ".netrc",
    ".pypirc",
    ".git-credentials",
    ".htpasswd",
}
_SENSITIVE_EXT = {".pem", ".key", ".p12", ".pfx", ".keystore"}

# 高置信度密钥/凭证模式（误报低）
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("私钥", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("OpenAI/Claude API Key", re.compile(r"sk-(?:ant-)?[A-Za-z0-9_\-]{20,}")),
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("腾讯云 SecretId", re.compile(r"\bAKID[A-Za-z0-9]{13,}\b")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitLab Token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{6,}\b")),
    (
        "疑似凭证赋值",
        re.compile(
            r"(?im)^[ \t]*(?:api[_-]?key|apikey|secret|token|password|passwd|pwd|"
            r"access[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]\s*"
            r"['\"]?[A-Za-z0-9/+_=\-]{16,}['\"]?[ \t]*$"
        ),
    ),
]

# 占位符特征（命中视为示例而非真实凭证）
_PLACEHOLDER_HINTS = ("<", "$", "{", "your", "example", "xxx", "replace", "todo", "changeme")

_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".woff", ".woff2", ".ttf", ".otf", ".zip", ".gz", ".tar", ".tgz",
    ".class", ".o", ".so", ".exe", ".dll", ".dylib", ".mp3", ".mp4",
}


def _reject_sensitive_files(files: dict[str, bytes]) -> None:
    """含敏感配置文件（.env/私钥等）即拒绝。"""
    hits: list[str] = []
    for path in files:
        p = PurePosixPath(path)
        name = p.name.lower()
        if name in _SENSITIVE_FILES or name.startswith(".env") or p.suffix.lower() in _SENSITIVE_EXT:
            hits.append(path)
    if hits:
        listing = "\n".join(f"  • {p}" for p in sorted(set(hits))[:10])
        raise ArchiveAnalyzeError(
            f"检测到敏感配置文件，已阻止上传：\n{listing}\n请移除后重新上传。"
        )


def _reject_secrets(files: dict[str, bytes]) -> None:
    """文本文件扫描疑似密钥/凭证，命中即拒绝。"""
    findings: list[str] = []
    for path, content in files.items():
        if PurePosixPath(path).suffix.lower() in _BINARY_EXTS:
            continue
        text = content.decode("utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                snippet = m.group(0).strip()
                if any(hint in snippet.lower() for hint in _PLACEHOLDER_HINTS):
                    continue
                shown = snippet[:37] + "..." if len(snippet) > 40 else snippet
                findings.append(f"  • {path} — {label}（{shown}）")
                if len(findings) >= 5:
                    break
            if len(findings) >= 5:
                break
        if len(findings) >= 5:
            break
    if findings:
        listing = "\n".join(findings)
        raise ArchiveAnalyzeError(
            f"检测到疑似敏感信息，已阻止上传：\n{listing}\n"
            "请移除真实凭证后重新上传（建议改用环境变量引用）。"
        )
