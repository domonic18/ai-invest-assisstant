"""技能优化建议单服务单测：快照落单、未处理单互斥、生成状态机与直派。"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.core.database import Base
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from app.models.account_quota import AdminAuditLog
from app.models.kb import KbOptimizationSuggestion, KbSource
from app.models.skill import Skill
from app.schemas.kb import KbOptimizationAgentOutput, KbOptimizationSuggestionItem
from app.schemas.skill import SkillFile, SkillFilesResponse
from app.services.kb import optimization_service
from app.services.kb.optimization_service import (
    OPEN_STATUSES,
    STATUS_FAILED,
    STATUS_PENDING_REVIEW,
    STATUS_QUEUED,
)
from app.services.skill.skill_service import SkillService

pytestmark = pytest.mark.unit


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element: Any, compiler: Any, **kw: Any) -> str:
    # Skill.custom_definition 用原生 JSONB，sqlite 建表时退化为 JSON 文本
    return "JSON"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                KbSource.__table__,
                Skill.__table__,
                KbOptimizationSuggestion.__table__,
                AdminAuditLog.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as db:
        yield db
    await engine.dispose()


async def _seed_skill(db: AsyncSession, *, skill_id: str = "market-daily-review") -> Skill:
    # skill.id 是 BigInteger PK，sqlite 不自动生成，显式给 id
    existing = (
        await db.execute(select(Skill).order_by(Skill.id.desc()).limit(1))
    ).scalar_one_or_none()
    next_id = (existing.id + 1) if existing else 1
    row = Skill(
        id=next_id,
        skill_id=skill_id,
        label="大盘复盘",
        kind="prompt_only",
        scenario="market",
        is_builtin=True,
        version=3,
    )
    db.add(row)
    await db.commit()
    return row


async def _seed_source(db: AsyncSession, *, enabled: bool = True) -> KbSource:
    row = KbSource(source_type="course", name="价值投资课", enabled=enabled)
    db.add(row)
    await db.commit()
    return row


def _fake_dispatch(calls: list[tuple[str, dict[str, Any]]]) -> Any:
    async def fake(
        session: object, task_name: str, params: dict[str, Any], **kwargs: object
    ) -> MagicMock:
        calls.append((task_name, params))
        return MagicMock(id=len(calls))

    return fake


# ---------------------------------------------------------------------------
# create_suggestion
# ---------------------------------------------------------------------------


async def test_create_suggestion_snapshots_and_dispatches(session: AsyncSession) -> None:
    skill = await _seed_skill(session)
    source = await _seed_source(session)
    calls: list[tuple[str, dict[str, Any]]] = []

    with patch(
        "collector.runtime.dispatcher.dispatch_collector_task",
        side_effect=_fake_dispatch(calls),
    ), patch.object(
        optimization_service, "_definition_snapshot", return_value="===== SKILL.md =====\nx"
    ) as snap:
        row = await optimization_service.create_suggestion(
            session, skill_id=skill.skill_id, source_id=source.id, actor_id=9
        )

    assert row.status == STATUS_QUEUED
    assert row.skill_id == "market-daily-review"
    assert row.skill_label == "大盘复盘"
    assert row.skill_kind == "builtin"
    assert row.skill_version == 3
    assert row.source_name == "价值投资课"
    assert row.skill_definition == "===== SKILL.md =====\nx"
    assert row.created_by == 9
    snap.assert_called_once()
    assert calls == [("kb-suggest", {"suggestion_id": row.id})]
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert [a.action for a in audits] == [optimization_service.AUDIT_OPTIMIZATION_CREATE]
    assert audits[0].detail["skillId"] == "market-daily-review"


async def test_create_suggestion_rejects_unknown_skill(session: AsyncSession) -> None:
    source = await _seed_source(session)
    with pytest.raises(NotFoundError, match="技能不存在"):
        await optimization_service.create_suggestion(
            session, skill_id="nope", source_id=source.id, actor_id=1
        )


async def test_create_suggestion_rejects_missing_source(session: AsyncSession) -> None:
    skill = await _seed_skill(session)
    with pytest.raises(NotFoundError, match="知识源不存在"):
        await optimization_service.create_suggestion(
            session, skill_id=skill.skill_id, source_id=999, actor_id=1
        )


async def test_create_suggestion_rejects_disabled_source(session: AsyncSession) -> None:
    skill = await _seed_skill(session)
    source = await _seed_source(session, enabled=False)
    with pytest.raises(UnprocessableEntityError, match="未启用"):
        await optimization_service.create_suggestion(
            session, skill_id=skill.skill_id, source_id=source.id, actor_id=1
        )


async def test_create_suggestion_conflicts_while_open(session: AsyncSession) -> None:
    skill = await _seed_skill(session)
    source = await _seed_source(session)
    for status in OPEN_STATUSES:
        session.add(
            KbOptimizationSuggestion(
                skill_id=skill.skill_id,
                skill_label=skill.label,
                skill_kind="builtin",
                skill_version=1,
                source_id=source.id,
                source_name=source.name,
                status=status,
                created_by=1,
            )
        )
    await session.commit()

    with pytest.raises(ConflictError, match="未处理建议单"):
        await optimization_service.create_suggestion(
            session, skill_id=skill.skill_id, source_id=source.id, actor_id=1
        )

    # 未处理单处理完（置终态）后可再发；终态（applied/rejected/failed）不阻塞
    for row in (
        await session.execute(
            select(KbOptimizationSuggestion).where(
                KbOptimizationSuggestion.skill_id == skill.skill_id
            )
        )
    ).scalars().all():
        row.status = "applied"
    await session.commit()
    calls: list[tuple[str, dict[str, Any]]] = []
    with patch(
        "collector.runtime.dispatcher.dispatch_collector_task",
        side_effect=_fake_dispatch(calls),
    ), patch.object(optimization_service, "_definition_snapshot", return_value=None):
        row = await optimization_service.create_suggestion(
            session, skill_id=skill.skill_id, source_id=source.id, actor_id=1
        )
    assert row.status == STATUS_QUEUED
    # 不同技能不受互斥约束
    other = await _seed_skill(session, skill_id="anomaly-attribution")
    with patch(
        "collector.runtime.dispatcher.dispatch_collector_task",
        side_effect=_fake_dispatch(calls),
    ), patch.object(optimization_service, "_definition_snapshot", return_value=None):
        row2 = await optimization_service.create_suggestion(
            session, skill_id=other.skill_id, source_id=source.id, actor_id=1
        )
    assert row2.status == STATUS_QUEUED


# ---------------------------------------------------------------------------
# run_generation
# ---------------------------------------------------------------------------


def _output() -> KbOptimizationAgentOutput:
    return KbOptimizationAgentOutput(
        summary="整体加强引用规范",
        suggestions=[
            KbOptimizationSuggestionItem(
                target_file="prompt.yaml",
                section="分析框架",
                original_text="旧文",
                suggested_text="新文",
                reason="缺少量价确认",
                citations=["《价值投资课》 第3集 05:30-06:10"],
            )
        ],
    )


async def _seed_suggestion(
    db: AsyncSession, *, status: str = STATUS_QUEUED
) -> KbOptimizationSuggestion:
    skill = await _seed_skill(db)
    source = await _seed_source(db)
    row = KbOptimizationSuggestion(
        skill_id=skill.skill_id,
        skill_label=skill.label,
        skill_kind="builtin",
        skill_version=1,
        source_id=source.id,
        source_name=source.name,
        status=status,
        created_by=1,
    )
    db.add(row)
    await db.commit()
    return row


async def test_run_generation_not_found(session: AsyncSession) -> None:
    stats = await optimization_service.run_generation(session, 424242)
    assert stats == {"notFound": 1}


async def test_run_generation_skips_non_queued(session: AsyncSession) -> None:
    row = await _seed_suggestion(session, status="generating")
    stats = await optimization_service.run_generation(session, row.id)
    assert stats == {"skippedStatus": "generating"}


async def test_run_generation_no_model_marks_failed(session: AsyncSession) -> None:
    row = await _seed_suggestion(session)
    with patch(
        "app.services.kb.optimization_service.resolve_role_model",
        AsyncMock(side_effect=UnprocessableEntityError("未配置 extract 模型角色")),
    ):
        stats = await optimization_service.run_generation(session, row.id)
    assert stats["failed"] == 1
    stored = await session.get(KbOptimizationSuggestion, row.id)
    assert stored.status == STATUS_FAILED
    assert "extract" in stored.error


async def test_run_generation_success_pends_review(session: AsyncSession) -> None:
    row = await _seed_suggestion(session)
    config = MagicMock(provider="kimi", model_name="k2", protocol="anthropic")
    with patch(
        "app.services.kb.optimization_service.resolve_role_model",
        AsyncMock(return_value=config),
    ), patch.object(
        optimization_service, "_generate", AsyncMock(return_value=_output())
    ) as gen:
        stats = await optimization_service.run_generation(session, row.id)

    assert stats == {"suggestions": 1}
    gen.assert_awaited_once()
    stored = await session.get(KbOptimizationSuggestion, row.id)
    assert stored.status == STATUS_PENDING_REVIEW
    assert stored.model_name == "kimi/k2"
    assert stored.summary == "整体加强引用规范"
    assert stored.suggestions[0]["target_file"] == "prompt.yaml"
    assert stored.error is None


async def test_run_generation_agent_failure_marks_failed(session: AsyncSession) -> None:
    row = await _seed_suggestion(session)
    config = MagicMock(provider="kimi", model_name="k2", protocol="anthropic")
    with patch(
        "app.services.kb.optimization_service.resolve_role_model",
        AsyncMock(return_value=config),
    ), patch.object(
        optimization_service,
        "_generate",
        AsyncMock(side_effect=RuntimeError("x" * 800)),
    ):
        stats = await optimization_service.run_generation(session, row.id)
    assert stats["failed"] == 1
    stored = await session.get(KbOptimizationSuggestion, row.id)
    assert stored.status == STATUS_FAILED
    assert len(stored.error) == 500  # 截断留档


# ---------------------------------------------------------------------------
# list / get
# ---------------------------------------------------------------------------


async def test_list_and_get_suggestion(session: AsyncSession) -> None:
    row = await _seed_suggestion(session)
    rows, total = await optimization_service.list_suggestions(
        session, status=STATUS_QUEUED, page=1, page_size=10
    )
    assert total == 1 and rows[0].id == row.id
    _, total_all = await optimization_service.list_suggestions(
        session, status="applied", page=1, page_size=10
    )
    assert total_all == 0

    got = await optimization_service.get_suggestion(session, row.id)
    assert got.skill_id == row.skill_id
    with pytest.raises(NotFoundError):
        await optimization_service.get_suggestion(session, 999_999)


# ---------------------------------------------------------------------------
# review（H3：通过/修订后应用/驳回）
# ---------------------------------------------------------------------------


def _pending_item(target: str = "SKILL.md", original: str = "旧文") -> dict[str, Any]:
    return {
        "target_file": target,
        "section": "章节",
        "original_text": original,
        "suggested_text": "新文",
        "reason": "r",
        "citations": [],
    }


async def _seed_pending(
    db: AsyncSession,
    *,
    suggestions: list[dict[str, Any]],
    is_builtin: bool = False,
    custom_definition: dict[str, Any] | None = None,
) -> KbOptimizationSuggestion:
    skill = await _seed_skill(db, skill_id="opt-skill")
    skill.is_builtin = is_builtin
    skill.custom_definition = custom_definition
    db.add(skill)
    await db.commit()
    source = await _seed_source(db)
    row = KbOptimizationSuggestion(
        skill_id=skill.skill_id,
        skill_label=skill.label,
        skill_kind="builtin" if is_builtin else "custom",
        skill_version=skill.version,
        source_id=source.id,
        source_name=source.name,
        status=STATUS_PENDING_REVIEW,
        suggestions=suggestions,
        created_by=1,
    )
    db.add(row)
    await db.commit()
    return row


async def test_review_reject_stamps_and_audits(session: AsyncSession) -> None:
    row = await _seed_pending(session, suggestions=[_pending_item()])
    out = await optimization_service.review_suggestion(
        session, row.id, action="reject", note="口径不符", revisions={}, actor_id=5
    )
    assert out.status == "rejected"
    assert out.review_note == "口径不符"
    assert out.reviewed_by == 5 and out.reviewed_at is not None
    assert out.apply_result is None
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert audits[-1].action == optimization_service.AUDIT_OPTIMIZATION_REJECT

    # 终态不可再审
    with pytest.raises(ConflictError, match="pending_review"):
        await optimization_service.review_suggestion(
            session, row.id, action="reject", note="再驳", revisions={}, actor_id=5
        )


async def test_review_reject_requires_note(session: AsyncSession) -> None:
    row = await _seed_pending(session, suggestions=[_pending_item()])
    with pytest.raises(UnprocessableEntityError, match="理由"):
        await optimization_service.review_suggestion(
            session, row.id, action="reject", note="  ", revisions={}, actor_id=1
        )


async def test_review_apply_empty_suggestions_rejected(session: AsyncSession) -> None:
    row = await _seed_pending(session, suggestions=[])
    with pytest.raises(UnprocessableEntityError, match="无修改点"):
        await optimization_service.review_suggestion(
            session, row.id, action="apply", note=None, revisions={}, actor_id=1
        )


async def test_review_revision_index_out_of_range(session: AsyncSession) -> None:
    row = await _seed_pending(session, suggestions=[_pending_item()])
    with pytest.raises(UnprocessableEntityError, match="越界"):
        await optimization_service.review_suggestion(
            session, row.id, action="apply", note=None, revisions={3: "x"}, actor_id=1
        )


async def test_review_apply_custom_writes_definition_and_bumps_version(
    session: AsyncSession,
) -> None:
    definition = {"skill_md": "# 复盘\n旧文\n", "system_prompt": "你是投研助手。旧文\n"}
    row = await _seed_pending(
        session,
        suggestions=[
            _pending_item("SKILL.md", original="旧文"),
            _pending_item("prompt.yaml", original="你是投研助手。旧文"),
        ],
        is_builtin=False,
        custom_definition=definition,
    )
    out = await optimization_service.review_suggestion(
        session, row.id, action="apply", note=None, revisions={}, actor_id=4
    )
    assert out.status == "applied"
    assert out.apply_result["kind"] == "custom_applied"
    assert out.apply_result["skillVersion"] == 4  # 快照 v3 + 1
    assert out.apply_result["appliedCount"] == 2
    stored_skill = (
        await session.execute(select(Skill).where(Skill.skill_id == "opt-skill"))
    ).scalar_one()
    assert stored_skill.version == 4
    assert "新文" in stored_skill.custom_definition["skill_md"]
    assert stored_skill.custom_definition["system_prompt"] == "新文\n"  # 原文整段被替换
    audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert audits[-1].action == optimization_service.AUDIT_OPTIMIZATION_APPLY


async def test_review_apply_custom_with_revision(session: AsyncSession) -> None:
    definition = {"skill_md": "旧文", "system_prompt": "s"}
    row = await _seed_pending(
        session,
        suggestions=[_pending_item("SKILL.md", original="旧文")],
        is_builtin=False,
        custom_definition=definition,
    )
    out = await optimization_service.review_suggestion(
        session,
        row.id,
        action="apply",
        note=None,
        revisions={0: "修订后的文本"},
        actor_id=4,
    )
    assert out.status == "applied"
    assert out.suggestions[0]["suggested_text"] == "修订后的文本"  # 应用产物留档
    stored_skill = (
        await session.execute(select(Skill).where(Skill.skill_id == "opt-skill"))
    ).scalar_one()
    assert stored_skill.custom_definition["skill_md"] == "修订后的文本"


async def test_review_apply_custom_missing_original_is_atomic(session: AsyncSession) -> None:
    definition = {"skill_md": "完全不同的内容", "system_prompt": "s"}
    row = await _seed_pending(
        session,
        suggestions=[_pending_item("SKILL.md", original="旧文")],
        is_builtin=False,
        custom_definition=definition,
    )
    with pytest.raises(ConflictError, match="整单不生效"):
        await optimization_service.review_suggestion(
            session, row.id, action="apply", note=None, revisions={}, actor_id=4
        )
    stored = await session.get(KbOptimizationSuggestion, row.id)
    assert stored.status == STATUS_PENDING_REVIEW  # 整单不生效
    stored_skill = (
        await session.execute(select(Skill).where(Skill.skill_id == "opt-skill"))
    ).scalar_one()
    assert stored_skill.version == 3
    assert stored_skill.custom_definition["skill_md"] == "完全不同的内容"


async def test_review_apply_skill_missing_conflicts(session: AsyncSession) -> None:
    row = await _seed_pending(session, suggestions=[_pending_item()])
    await session.execute(
        Skill.__table__.delete().where(Skill.skill_id == "opt-skill")
    )
    await session.commit()
    with pytest.raises(ConflictError, match="不存在"):
        await optimization_service.review_suggestion(
            session, row.id, action="apply", note=None, revisions={}, actor_id=4
        )


async def test_review_apply_version_drift_conflicts(session: AsyncSession) -> None:
    row = await _seed_pending(
        session,
        suggestions=[_pending_item()],
        is_builtin=False,
        custom_definition={"skill_md": "旧文", "system_prompt": "s"},
    )
    skill = (
        await session.execute(select(Skill).where(Skill.skill_id == "opt-skill"))
    ).scalar_one()
    skill.version = 9  # 生成后被他人更新
    await session.commit()
    with pytest.raises(ConflictError, match="漂移"):
        await optimization_service.review_suggestion(
            session, row.id, action="apply", note=None, revisions={}, actor_id=4
        )


async def test_review_apply_builtin_exports_full_files(session: AsyncSession) -> None:
    row = await _seed_pending(
        session, suggestions=[_pending_item("SKILL.md", original="旧文")], is_builtin=True
    )
    fake_files = SkillFilesResponse(
        skill_id="opt-skill",
        is_builtin=True,
        synthetic=False,
        files=[SkillFile(path="SKILL.md", size=6, content="开头\n旧文\n结尾")],
    )
    with patch.object(
        SkillService, "_builtin_files", return_value=fake_files
    ) as p_files:
        out = await optimization_service.review_suggestion(
            session, row.id, action="apply", note=None, revisions={}, actor_id=4
        )
    p_files.assert_called_once_with("opt-skill")
    assert out.status == "applied"
    assert out.apply_result["kind"] == "builtin_export"
    assert out.apply_result["appliedCount"] == 1
    exported = {f["path"]: f["content"] for f in out.apply_result["files"]}
    assert exported["SKILL.md"] == "开头\n新文\n结尾"  # 应用后全文（运行时不落盘）


async def test_review_apply_builtin_unknown_target_conflicts(session: AsyncSession) -> None:
    row = await _seed_pending(
        session,
        suggestions=[_pending_item("scripts/run.py", original="旧文")],
        is_builtin=True,
    )
    fake_files = SkillFilesResponse(
        skill_id="opt-skill",
        is_builtin=True,
        synthetic=False,
        files=[SkillFile(path="SKILL.md", size=6, content="开头\n旧文\n结尾")],
    )
    with patch.object(SkillService, "_builtin_files", return_value=fake_files):
        with pytest.raises(ConflictError, match="不在技能包"):
            await optimization_service.review_suggestion(
                session, row.id, action="apply", note=None, revisions={}, actor_id=4
            )
