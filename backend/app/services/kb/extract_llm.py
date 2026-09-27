"""抽取链路 LLM 交互层（prompt 构造 + ``run_structured`` 调用封装）。

只做「把什么文本喂给模型、调哪个 result_type」；编排（何时调、失败怎么记账）
在 ``extract_service`` / ``extract_points``。模型调用统一经 ``meter_scope``
计费（KB 抽取特性）。
"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb import KbMedia
from app.services.kb.extract_pipeline import WindowSegment
from app.services.quota.constants import FEATURE_KB_EXTRACT
from app.services.quota.context import meter_scope


async def outline_for_media(
    session: AsyncSession,
    config: Any,
    media: KbMedia,
    segments: list[Any],
) -> Any:
    """单集大纲：全文阅读后输出条目列表（episode_no 由 prompt 固定）。"""
    from app.agent.runtime.structured import run_structured
    from app.schemas.kb import EpisodeOutline

    episode_no = media.episode_no or 0
    numbered = "\n".join(f"{i}. {seg.text}" for i, seg in enumerate(segments, start=1))
    prompt = (
        f"你是课程目录编辑。阅读第 {episode_no} 集「{media.title}」的逐句文稿，"
        "提炼本集知识大纲：3~8 个条目、按讲解顺序，每条含 title（小节标题）与"
        " summary（一句话概括）。episode_no 固定输出 "
        f"{episode_no}。只依据文稿内容，不要编造。\n\n文稿：\n{numbered}"
    )
    with meter_scope(
        None,
        FEATURE_KB_EXTRACT,
        detail={"sourceId": media.source_id, "mediaId": media.id},
    ):
        return await run_structured(
            session, result_type=EpisodeOutline, user_prompt=prompt,
            config_id=config.id,
        )


def chapter_merge_prompt(
    base: list[dict[str, Any]] | None, outline_payload: list[dict[str, Any]]
) -> str:
    """章节合并 prompt：有已有树时增量归并，否则全量合并为目录树。"""
    if base:
        return (
            "你是全书目录主编。下面是本书已有目录树，以及新到各集的大纲"
            "（JSON 数组）。请把新集内容合并进目录树：顶层 3~10 个章节，"
            "每章 children 为该章下的小节列表（可为空数组）。只增补新集"
            "涉及的章节/小节，已有章节标题保持稳定（下游按章节引用），"
            "不要编造大纲之外的内容。\n\n"
            f"已有目录树：\n{render_tree(base)}\n\n"
            "新到各集大纲：\n"
            f"{_dumps(outline_payload)}"
        )
    return (
        "你是全书目录主编。以下是同一课程各集大纲（JSON 数组），请合并为"
        "全书目录树：顶层 3~10 个章节，每章 children 为该章下的小节列表"
        "（可为空数组）。章节/小节标题从大纲条目归纳提升，不要照抄全部条目，"
        "也不要编造大纲之外的内容。\n\n"
        f"{_dumps(outline_payload)}"
    )


def window_prompt(
    media: KbMedia,
    window: list[WindowSegment],
    chapters: list[dict[str, Any]],
) -> str:
    lines = []
    for seg in window:
        timecode = _fmt_ms(seg.start_ms) if seg.start_ms is not None else "P?"
        lines.append(f"[{timecode}] {seg.text}")
    return (
        "你是金融课程知识整理员。从下面的文稿片段中抽取可独立成立的知识点卡片。\n"
        "要求：\n"
        "- point_type 取 concept/theorem/method/discipline/case 之一\n"
        "- excerpt 必须原样摘抄文稿中**连续的 1~3 句**原文：不得改写、"
        "不得删节；确需跳过中间句时用「……」连接，且每个片段也要整句原文\n"
        "- start_ms/end_ms 为该知识点讲解起止毫秒时间码，按各行行首 [mm:ss] "
        "估算；无法判断输出 null\n"
        "- chapter_path 从下方目录树选择该知识点所属章节，输出根到该节点的"
        " id 链（如 [\"1\", \"1.2\"]）；确实无法归入任何章节输出空列表\n"
        "- confidence 为本卡片整体正确性的自评，取 high/medium/low；"
        "文稿依据不足或需跨段推断时降档\n"
        "- related_titles 填与之相关的其他知识点标题，可为空列表\n"
        "- term_definition/applicable_scene 无内容输出空串\n"
        "- 不编造文稿中没有的内容；本窗口没有新知识点时输出空 points\n\n"
        f"目录树（缩进表示层级，格式为 id: 标题）：\n{render_tree(chapters)}\n\n"
        f"课程「{media.title}」文稿（行首为该句起始时间）：\n" + "\n".join(lines)
    )


def render_tree(nodes: list[dict[str, Any]], depth: int = 0) -> str:
    parts: list[str] = []
    for node in nodes:
        parts.append("  " * depth + f"{node['id']}: {node['title']}")
        parts.extend(render_tree(node.get("children") or [], depth + 1))
    return "\n".join(parts)


def _dumps(payload: list[dict[str, Any]]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "?"
    total_seconds = ms // 1000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
