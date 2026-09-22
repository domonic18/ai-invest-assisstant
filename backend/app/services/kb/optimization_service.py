"""技能优化建议单（F-KB-07 批次 H2/H3，arch/12 §9）。

后台选「目标技能 × 知识源」手动触发：本服务落建议单（skill/source 全
快照，留档可溯）并直派 Celery ``kb-suggest`` 任务；worker 侧
``run_generation`` 组装优化 Agent（deepagents + ``search_knowledge_base``
工具，模型取知识库设置 extract 槽位）读技能定义检索知识源，产出修改点
列表后置 pending_review 交人工审核（批次 H3 审核与应用）。

同一技能存在未处理单（queued/generating/pending_review）时禁止新发。
审核（review_suggestion）：通过/修订后应用/驳回；custom 技能 version+1
直写生效，builtin 只导出应用后全文交开发落库（运行时不改代码库文件）。
"""

from datetime import datetime, timezone
from typing import Any, cast

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.core.prompt_loader import get_prompt_loader
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.kb import KbOptimizationSuggestion, KbSource
from app.models.skill import Skill
from app.schemas.kb import KbOptimizationAgentOutput
from app.services.admin.audit_service import record_audit
from app.services.kb.settings_service import resolve_role_model

logger = structlog.get_logger(__name__)

STATUS_QUEUED = "queued"
STATUS_GENERATING = "generating"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_APPLIED = "applied"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"

#: 未处理状态：任一存在即禁止对该技能发起新一轮（arch/12 §9）
OPEN_STATUSES = (STATUS_QUEUED, STATUS_GENERATING, STATUS_PENDING_REVIEW)

AUDIT_OPTIMIZATION_CREATE = "kb.optimization.create"
AUDIT_OPTIMIZATION_APPLY = "kb.optimization.apply"
AUDIT_OPTIMIZATION_REJECT = "kb.optimization.reject"


async def create_suggestion(
    session: AsyncSession,
    *,
    skill_id: str,
    source_id: int,
    actor_id: int,
) -> KbOptimizationSuggestion:
    """落建议单并直派生成任务（状态机起点 queued）。

    Raises:
        NotFoundError: 技能或知识源不存在。
        ConflictError: 该技能存在未处理建议单。
        UnprocessableEntityError: 知识源未启用。
    """
    skill = (
        await session.execute(select(Skill).where(Skill.skill_id == skill_id))
    ).scalar_one_or_none()
    if skill is None:
        raise NotFoundError(f"技能不存在: {skill_id}")
    source = await session.get(KbSource, source_id)
    if source is None or source.deleted_at is not None:
        raise NotFoundError(f"知识源不存在: {source_id}")
    if not source.enabled:
        raise UnprocessableEntityError(f"知识源 {source.name} 未启用")
    open_row = (
        await session.execute(
            select(func.count())
            .select_from(KbOptimizationSuggestion)
            .where(
                KbOptimizationSuggestion.skill_id == skill_id,
                KbOptimizationSuggestion.status.in_(OPEN_STATUSES),
            )
        )
    ).scalar_one()
    if open_row:
        raise ConflictError(f"技能 {skill_id} 存在未处理建议单，处理完再发起新一轮")

    row = KbOptimizationSuggestion(
        skill_id=skill.skill_id,
        skill_label=skill.label,
        skill_kind="builtin" if skill.is_builtin else "custom",
        skill_version=skill.version,
        source_id=source.id,
        source_name=source.name,
        status=STATUS_QUEUED,
        skill_definition=_definition_snapshot(skill),
        created_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_OPTIMIZATION_CREATE,
        detail={"suggestionId": row.id, "skillId": skill_id, "sourceId": source_id},
    )
    await session.commit()

    # 直派 Celery（无 collector_task 行的按需任务，先例 market_dispatch_service）
    from collector.runtime.dispatcher import dispatch_collector_task

    await dispatch_collector_task(
        session, "kb-suggest", {"suggestion_id": row.id}
    )
    await session.refresh(row)
    return row


def _definition_snapshot(skill: Skill) -> str | None:
    """技能定义全文快照（builtin 读镜像文件；custom 由配置合成虚拟文件）。"""
    from app.services.skill.skill_service import SkillService

    try:
        files = (
            SkillService._builtin_files(skill.skill_id)
            if skill.is_builtin
            else SkillService._custom_files(skill)
        )
    except NotFoundError:
        return None
    return "\n\n".join(f"===== {f.path} =====\n{f.content}" for f in files.files)


async def run_generation(session: AsyncSession, suggestion_id: int) -> dict[str, Any]:
    """执行生成（Celery kb-suggest 入口）：queued 单置 generating 跑 Agent。

    幂等防重：非 queued 状态直接跳过；模型槽位缺失或 Agent 失败置 failed
    留错误文本（可删单重发）。
    """
    row = await session.get(KbOptimizationSuggestion, suggestion_id)
    if row is None:
        return {"notFound": 1}
    if row.status != STATUS_QUEUED:
        return {"skippedStatus": row.status}
    row.status = STATUS_GENERATING
    await session.commit()
    try:
        config = await resolve_role_model(session, "extract")
    except UnprocessableEntityError as exc:
        row.status = STATUS_FAILED
        row.error = str(exc)
        await session.commit()
        logger.warning("kb_optimize_no_model", suggestion_id=suggestion_id)
        return {"failed": 1, "error": str(exc)}
    try:
        output = await _generate(row, config)
    except Exception as exc:  # noqa: BLE001
        row.status = STATUS_FAILED
        row.error = str(exc)[:500]
        await session.commit()
        logger.warning(
            "kb_optimize_failed", suggestion_id=suggestion_id, error=str(exc)[:300]
        )
        return {"failed": 1, "error": str(exc)[:300]}
    row.suggestions = [item.model_dump() for item in output.suggestions]
    row.summary = output.summary
    row.model_name = f"{config.provider}/{config.model_name}"
    row.status = STATUS_PENDING_REVIEW
    await session.commit()
    logger.info(
        "kb_optimize_done",
        suggestion_id=suggestion_id,
        n_suggestions=len(output.suggestions),
    )
    return {"suggestions": len(output.suggestions)}


async def _generate(
    row: KbOptimizationSuggestion, config: Any
) -> KbOptimizationAgentOutput:
    """优化 Agent：deepagents 工具循环检索知识源 → 结构化修改点列表。"""
    from deepagents import create_deep_agent

    from app.agent.runtime.model_factory import build_langchain_model
    from app.agent.skills.skill_runtime import invoke_structured
    from app.agent.tools.kb_tools import search_knowledge_base
    from app.schemas.llm_config import LLMProtocol
    from app.services.admin.llm_config_service import ResolvedLLMConfig
    from app.services.quota.constants import FEATURE_KB_OPTIMIZE
    from app.services.quota.context import meter_scope
    from app.utils.crypto import decrypt_token

    prompt = get_prompt_loader().load("agents", "kb_optimization")
    user_prompt = prompt.user_prompt_template.format(
        skill_label=row.skill_label,
        skill_id=row.skill_id,
        skill_kind=row.skill_kind,
        skill_version=row.skill_version,
        source_name=row.source_name,
    )
    if row.skill_definition:
        user_prompt = f"{user_prompt}\n\n{row.skill_definition}"

    resolved = ResolvedLLMConfig(
        config_id=config.id,
        provider=config.provider,
        protocol=cast(LLMProtocol, config.protocol),
        base_url=config.base_url,
        api_key=decrypt_token(config.api_key_encrypted),
        model_name=config.model_name,
        extra=config.extra or {},
    )
    agent = create_deep_agent(
        model=build_langchain_model(resolved),
        tools=[search_knowledge_base],
        system_prompt=prompt.system_prompt,
        name="kb-optimization",
    )
    with meter_scope(
        None,
        FEATURE_KB_OPTIMIZE,
        detail={"sourceId": row.source_id, "skillId": row.skill_id},
    ):
        return cast(
            "KbOptimizationAgentOutput",
            await invoke_structured(
                agent,
                user_prompt,
                KbOptimizationAgentOutput,
                skill_id="kb-optimization",
                suggestion_id=row.id,
            ),
        )


async def list_suggestions(
    session: AsyncSession,
    *,
    status: str | None = None,
    page: int,
    page_size: int,
) -> tuple[list[KbOptimizationSuggestion], int]:
    """分页清单（created_at 倒序，状态过滤可选）。"""
    crits = []
    if status:
        crits.append(KbOptimizationSuggestion.status == status)
    total = (
        await session.execute(
            select(func.count()).select_from(KbOptimizationSuggestion).where(*crits)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(KbOptimizationSuggestion)
                .where(*crits)
                .order_by(KbOptimizationSuggestion.created_at.desc(), KbOptimizationSuggestion.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def get_suggestion(
    session: AsyncSession, suggestion_id: int
) -> KbOptimizationSuggestion:
    """按 ID 取建议单，缺失抛 NotFoundError。"""
    row = await session.get(KbOptimizationSuggestion, suggestion_id)
    if row is None:
        raise NotFoundError(f"建议单不存在: {suggestion_id}")
    return row


async def review_suggestion(
    session: AsyncSession,
    suggestion_id: int,
    *,
    action: str,
    note: str | None,
    revisions: dict[int, str],
    actor_id: int,
) -> KbOptimizationSuggestion:
    """审核建议单：apply（可带修订）/ reject；只有 pending_review 可审。

    custom 技能直写生效（version+1）；builtin 只导出应用后全文留档
    （apply_result.files），运行时不改代码库文件。

    Raises:
        NotFoundError: 建议单不存在。
        ConflictError: 状态非 pending_review、技能已删/版本漂移、或任一
            修改点原文在目标文件中找不到（防错位应用，整单不生效）。
        UnprocessableEntityError: reject 未给理由 / apply 无修改点 /
            修订下标越界。
    """
    row = await get_suggestion(session, suggestion_id)
    if row.status != STATUS_PENDING_REVIEW:
        raise ConflictError(f"建议单状态为 {row.status}，仅 pending_review 可审核")
    if action == "reject":
        if not note or not note.strip():
            raise UnprocessableEntityError("驳回必须填写理由")
        row.status = STATUS_REJECTED
        _stamp_review(row, actor_id, note)
        await record_audit(
            session,
            actor_id=actor_id,
            action=AUDIT_OPTIMIZATION_REJECT,
            detail={"suggestionId": row.id, "skillId": row.skill_id},
        )
        await session.commit()
        return row

    items = row.suggestions or []
    if not items:
        raise UnprocessableEntityError("建议单无修改点，无可应用内容")
    for idx in revisions:
        if idx >= len(items):
            raise UnprocessableEntityError(f"修订下标越界: {idx}")
    skill = (
        await session.execute(select(Skill).where(Skill.skill_id == row.skill_id))
    ).scalar_one_or_none()
    if skill is None:
        raise ConflictError(f"技能 {row.skill_id} 已不存在，无法应用")
    if skill.version != row.skill_version:
        raise ConflictError(
            f"技能版本已漂移（生成时 v{row.skill_version}，当前 v{skill.version}），请重新生成建议单"
        )

    applied_items = [dict(item) for item in items]
    for idx, text in revisions.items():
        applied_items[idx]["suggested_text"] = text

    if skill.is_builtin:
        apply_result = _apply_builtin(skill, row, applied_items)
    else:
        apply_result = await _apply_custom(session, skill, row, applied_items)

    row.suggestions = applied_items
    row.status = STATUS_APPLIED
    row.apply_result = apply_result
    _stamp_review(row, actor_id, note)
    await record_audit(
        session,
        actor_id=actor_id,
        action=AUDIT_OPTIMIZATION_APPLY,
        detail={
            "suggestionId": row.id,
            "skillId": row.skill_id,
            "kind": apply_result.get("kind"),
            "appliedCount": apply_result.get("appliedCount"),
        },
    )
    await session.commit()
    await session.refresh(row)
    return row


def _stamp_review(row: KbOptimizationSuggestion, actor_id: int, note: str | None) -> None:
    row.reviewed_by = actor_id
    row.reviewed_at = datetime.now(timezone.utc)
    row.review_note = note


def _apply_text(content: str, item: dict[str, Any], idx: int) -> str:
    """单条修改点应用到目标文本（新增类追加文末；替换类全量替换）。

    Raises:
        ConflictError: 原文在目标文本中找不到（生成后定义已变，防错位）。
    """
    original = str(item.get("original_text") or "")
    suggested = str(item["suggested_text"])
    if not original:
        return f"{content.rstrip()}\n\n{suggested.strip()}\n" if content else suggested
    if original not in content:
        raise ConflictError(
            f"修改点 #{idx + 1} 原文在 {item['target_file']} 中找不到，定义已漂移，整单不生效"
        )
    return content.replace(original, suggested)


def _apply_builtin(
    skill: Skill,
    row: KbOptimizationSuggestion,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """builtin：读代码库技能包文件，应用替换后全文导出留档（不写文件）。"""
    from app.services.skill.skill_service import SkillService

    files = SkillService._builtin_files(skill.skill_id)
    by_path = {f.path: f.content for f in files.files}
    for idx, item in enumerate(items):
        target = str(item["target_file"])
        if target not in by_path:
            raise ConflictError(
                f"修改点 #{idx + 1} 目标文件 {target} 不在技能包中，整单不生效"
            )
        by_path[target] = _apply_text(by_path[target], item, idx)
    return {
        "kind": "builtin_export",
        "appliedCount": len(items),
        "note": "builtin 技能运行时不改文件：以下为应用后完整文件文本，交开发核对后落库",
        "files": [
            {"path": path, "content": content} for path, content in sorted(by_path.items())
        ],
    }


async def _apply_custom(
    session: AsyncSession,
    skill: Skill,
    row: KbOptimizationSuggestion,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """custom：修改点映射到 custom_definition 字段，version+1 直写生效。

    SKILL.md → ``skill_md``；prompt.yaml → ``system_prompt`` /
    ``user_prompt_template``（按原文所在处；新增类仅支持 SKILL.md）。
    """
    definition: dict[str, Any] = dict(skill.custom_definition or {})
    field_map: dict[str, list[str]] = {
        "SKILL.md": ["skill_md"],
        "prompt.yaml": ["system_prompt", "user_prompt_template"],
    }
    for idx, item in enumerate(items):
        target = str(item["target_file"])
        candidates = field_map.get(target)
        if not candidates:
            raise ConflictError(
                f"修改点 #{idx + 1} 目标文件 {target} 不受支持（custom 仅 SKILL.md/prompt.yaml）"
            )
        original = str(item.get("original_text") or "")
        if not original and target != "SKILL.md":
            raise ConflictError(
                f"修改点 #{idx + 1} 新增类建议仅支持 SKILL.md，整单不生效"
            )
        applied = False
        for field in candidates:
            current = str(definition.get(field) or "")
            if not original or original in current:
                definition[field] = _apply_text(current, item, idx)
                applied = True
                break
        if not applied:
            raise ConflictError(
                f"修改点 #{idx + 1} 原文未落在 {target} 的任何字段中，整单不生效"
            )
    skill.custom_definition = definition
    skill.version += 1
    await session.flush()
    return {
        "kind": "custom_applied",
        "appliedCount": len(items),
        "skillVersion": skill.version,
    }
