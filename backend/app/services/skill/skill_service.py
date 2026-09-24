"""Skill 广场与用户技能服务：列表分组、安装/卸载、custom CRUD。

custom skill = 配置（``custom_definition`` JSONB），非代码；执行沙箱/
allowed_tools 执法等延后批次。事务边界在本层（成功显式 commit）。
"""

from typing import Any

import structlog
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.skill import Skill, UserSkill
from app.repositories.skill import SkillRepository, UserSkillRepository
from app.schemas.skill import (
    CustomSkillCreateRequest,
    CustomSkillUpdateRequest,
    SkillFile,
    SkillFilesResponse,
    SkillItem,
    SkillResponse,
    SkillSquareResponse,
    UserSkillResponse,
)
from app.skills import builtin_skill_ids

logger = structlog.get_logger(__name__)

_CUSTOM_DEFINITION_SCHEMA_VERSION = 1

# 文件浏览仅服务文本类文件（本模块私有的安全契约；大小/数量上限走 Settings）
SKILL_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt", ".py", ".j2", ".tmpl"}


class SkillService:
    """技能广场与用户安装关系业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.skills = SkillRepository(session)
        self.installs = UserSkillRepository(session)

    async def list_skills(self, user_id: int) -> SkillSquareResponse:
        """广场（available）= 已发布 builtin + 他人已发布 custom；
        我的（mine）= 已安装（带 enabled）+ 本人全部 custom（含未发布）。"""
        published = await self.skills.list_published()
        own = await self.skills.list_by_owner(user_id)
        installed = await self.installs.list_installed(user_id)
        install_by_id = {row.skill_id: row for row in installed}

        rows: dict[str, Skill] = {row.skill_id: row for row in published}
        rows.update({row.skill_id: row for row in own})
        for install in installed:
            if install.skill_id not in rows:
                row = await self.skills.get_by_skill_id(install.skill_id)
                if row is not None:
                    rows[install.skill_id] = row

        mine = [
            self._item(rows[install.skill_id], install)
            for install in installed
            if install.skill_id in rows
        ]
        mine += [self._item(row) for row in own if row.skill_id not in install_by_id]

        available = [
            self._item(row, install_by_id.get(row.skill_id))
            for row in published
            if row.owner_user_id != user_id
        ]
        return SkillSquareResponse(available=available, mine=mine)

    async def get_skill_detail(self, user_id: int, skill_id: str) -> SkillResponse:
        """技能详情：未发布技能仅属主可见。"""
        row = await self._get_visible_skill(user_id, skill_id)
        return SkillResponse.model_validate(row)

    async def get_skill_files(self, user_id: int, skill_id: str) -> SkillFilesResponse:
        """技能包文件浏览：builtin 读镜像内 ``skills/<id>/`` 目录；
        custom 由 ``custom_definition`` 合成虚拟文件（SKILL.md + prompt.yaml）。

        Raises:
            NotFoundError: 技能不存在/不可见，或 builtin 目录缺失。
        """
        row = await self._get_visible_skill(user_id, skill_id)
        if row.is_builtin:
            return self._builtin_files(row.skill_id)
        return self._custom_files(row)

    @staticmethod
    def _builtin_files(skill_id: str) -> SkillFilesResponse:
        settings = get_settings()
        base = settings.skills_dir.resolve()
        root = (base / skill_id).resolve()
        # skill_id 经 DB 行校验（create 有 kebab-case pattern），此处再钉一次目录边界
        if not root.is_relative_to(base) or not root.is_dir():
            raise NotFoundError(f"技能包文件缺失: {skill_id}")

        files: list[SkillFile] = []
        for path in sorted(root.rglob("*")):
            if len(files) >= settings.skill_files_max_count:
                break
            if (
                not path.is_file()
                or path.name.startswith(".")
                or path.suffix.lower() not in SKILL_TEXT_SUFFIXES
            ):
                continue
            data = path.read_bytes()
            if len(data) > settings.skill_file_max_bytes:
                continue
            files.append(
                SkillFile(
                    path=path.relative_to(root).as_posix(),
                    size=len(data),
                    content=data.decode("utf-8", errors="replace"),
                )
            )
        return SkillFilesResponse(
            skill_id=skill_id, is_builtin=True, synthetic=False, files=files
        )

    @staticmethod
    def _custom_files(row: Skill) -> SkillFilesResponse:
        """由 ``custom_definition`` JSONB 合成虚拟技能包文件。"""
        definition: dict[str, Any] = row.custom_definition or {}
        prompt: dict[str, Any] = {"id": row.skill_id, "name": row.label, "version": row.version}
        if row.description:
            prompt["description"] = row.description
        for key in ("sections", "allowed_tools", "system_prompt", "user_prompt_template"):
            if definition.get(key):
                prompt[key] = definition[key]
        prompt_yaml = yaml.safe_dump(prompt, allow_unicode=True, sort_keys=False)
        skill_md = str(definition.get("skill_md", ""))

        files = [
            SkillFile(
                path="SKILL.md",
                size=len(skill_md.encode("utf-8")),
                content=skill_md,
            ),
            SkillFile(
                path="prompt.yaml",
                size=len(prompt_yaml.encode("utf-8")),
                content=prompt_yaml,
            ),
        ]
        return SkillFilesResponse(
            skill_id=row.skill_id, is_builtin=False, synthetic=True, files=files
        )

    async def install_skill(self, user_id: int, skill_id: str) -> UserSkillResponse:
        """安装技能（本人未发布 custom 允许自装）。

        Raises:
            NotFoundError: 技能不存在或不可见。
            ConflictError: 已安装。
        """
        row = await self.skills.get_by_skill_id(skill_id)
        if row is None or (not row.published and row.owner_user_id != user_id):
            raise NotFoundError(f"技能不存在或不可安装: {skill_id}")
        if await self.installs.get_install(user_id, skill_id) is not None:
            raise ConflictError(f"技能已安装: {skill_id}")

        install = UserSkill(user_id=user_id, skill_id=skill_id)
        self.session.add(install)
        await self.session.commit()
        logger.info("skill_installed", user_id=user_id, skill_id=skill_id)
        return UserSkillResponse(skill_id=skill_id, installed=True, enabled=True)

    async def uninstall_skill(self, user_id: int, skill_id: str) -> UserSkillResponse:
        """卸载技能。

        Raises:
            NotFoundError: 未安装。
        """
        install = await self.installs.get_install(user_id, skill_id)
        if install is None:
            raise NotFoundError(f"技能未安装: {skill_id}")
        enabled = install.enabled
        await self.installs.delete(install)
        await self.session.commit()
        logger.info("skill_uninstalled", user_id=user_id, skill_id=skill_id)
        return UserSkillResponse(skill_id=skill_id, installed=False, enabled=enabled)

    async def toggle_install_skill(
        self, user_id: int, skill_id: str, enabled: bool
    ) -> UserSkillResponse:
        """启用/停用已安装技能（不改安装关系）。

        Raises:
            NotFoundError: 未安装。
        """
        install = await self.installs.get_install(user_id, skill_id)
        if install is None:
            raise NotFoundError(f"技能未安装: {skill_id}")
        install.enabled = enabled
        await self.session.commit()
        logger.info(
            "skill_install_toggled",
            user_id=user_id,
            skill_id=skill_id,
            enabled=enabled,
        )
        return UserSkillResponse(skill_id=skill_id, installed=True, enabled=enabled)

    async def create_custom_skill(
        self, user_id: int, payload: CustomSkillCreateRequest
    ) -> SkillResponse:
        """创建 custom skill（draft 态，published=False）。

        Raises:
            ConflictError: skill_id 撞 builtin 保留字或已存在技能。
        """
        if payload.skill_id in builtin_skill_ids():
            raise ConflictError(f"skill_id 与 builtin 技能冲突: {payload.skill_id}")
        if await self.skills.get_by_skill_id(payload.skill_id) is not None:
            raise ConflictError(f"skill_id 已存在: {payload.skill_id}")

        row = Skill(
            skill_id=payload.skill_id,
            label=payload.label,
            kind="custom",
            scenario="custom",
            description=payload.description,
            is_builtin=False,
            owner_user_id=user_id,
            published=False,
            custom_definition=self._definition_payload(payload.custom_definition),
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        logger.info("custom_skill_created", user_id=user_id, skill_id=row.skill_id)
        return SkillResponse.model_validate(row)

    async def update_custom_skill(
        self, user_id: int, skill_id: str, payload: CustomSkillUpdateRequest
    ) -> SkillResponse:
        """更新本人 custom skill（version+1；None 字段不变）。

        Raises:
            NotFoundError: 技能不存在或非本人 custom。
        """
        row = await self._get_own_custom(user_id, skill_id)
        if payload.label is not None:
            row.label = payload.label
        if payload.description is not None:
            row.description = payload.description
        if payload.custom_definition is not None:
            row.custom_definition = self._definition_payload(payload.custom_definition)
        row.version += 1
        await self.session.commit()
        await self.session.refresh(row)
        return SkillResponse.model_validate(row)

    async def publish_custom_skill(self, user_id: int, skill_id: str) -> SkillResponse:
        """发布本人 custom skill（幂等，不可下架——下架态延后批次）。

        Raises:
            NotFoundError: 技能不存在或非本人 custom。
        """
        row = await self._get_own_custom(user_id, skill_id)
        if not row.published:
            row.published = True
            await self.session.commit()
            await self.session.refresh(row)
            logger.info("custom_skill_published", user_id=user_id, skill_id=skill_id)
        return SkillResponse.model_validate(row)

    async def _get_visible_skill(self, user_id: int, skill_id: str) -> Skill:
        row = await self.skills.get_by_skill_id(skill_id)
        if row is None or (not row.published and row.owner_user_id != user_id):
            raise NotFoundError(f"技能不存在: {skill_id}")
        return row

    async def _get_own_custom(self, user_id: int, skill_id: str) -> Skill:
        row = await self.skills.get_by_skill_id(skill_id)
        if row is None or row.is_builtin or row.owner_user_id != user_id:
            # 他人/内置技能统一 404，不泄露存在性
            raise NotFoundError(f"技能不存在: {skill_id}")
        return row

    @staticmethod
    def _item(row: Skill, install: UserSkill | None = None) -> SkillItem:
        return SkillItem(
            skill_id=row.skill_id,
            label=row.label,
            kind=row.kind,
            scenario=row.scenario,
            is_builtin=row.is_builtin,
            published=row.published,
            installed=install is not None,
            enabled=install.enabled if install is not None else None,
            description=row.description,
        )

    @staticmethod
    def _definition_payload(definition: Any) -> dict[str, Any]:
        return {**definition.model_dump(), "schema_version": _CUSTOM_DEFINITION_SCHEMA_VERSION}
