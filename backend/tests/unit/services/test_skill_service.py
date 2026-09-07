"""SkillService 契约测试：安装冲突/可见性 404、custom 属主校验、广场分组。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.models.skill import Skill, UserSkill
from app.schemas.skill import CustomSkillCreateRequest, CustomSkillDefinition
from app.services.skill.skill_service import SkillService

_NOW = datetime.now(timezone.utc)


def _builtin(skill_id: str = "market-daily-review", published: bool = True) -> Skill:
    return Skill(
        skill_id=skill_id,
        label="大盘每日复盘",
        kind="executable",
        is_builtin=True,
        published=published,
        sort=1,
        version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _custom(
    skill_id: str = "my-skill", owner_user_id: int = 2, published: bool = False
) -> Skill:
    return Skill(
        skill_id=skill_id,
        label="自定义",
        kind="custom",
        is_builtin=False,
        owner_user_id=owner_user_id,
        published=published,
        version=1,
        custom_definition={"skill_md": "s", "system_prompt": "p"},
        created_at=_NOW,
        updated_at=_NOW,
    )


def _install(user_id: int, skill_id: str, enabled: bool = True) -> UserSkill:
    return UserSkill(user_id=user_id, skill_id=skill_id, enabled=enabled)


@pytest.fixture
def service() -> SkillService:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    def _stamp(obj: object) -> None:
        if isinstance(obj, (Skill, UserSkill)):
            obj.created_at = obj.created_at or _NOW
            obj.updated_at = obj.updated_at or _NOW
        if isinstance(obj, Skill) and obj.version is None:
            obj.version = 1

    session.add = MagicMock(side_effect=_stamp)
    svc = SkillService(session)
    svc.skills = AsyncMock()
    svc.installs = AsyncMock()
    return svc


@pytest.mark.unit
@pytest.mark.asyncio
class TestInstallSkill:
    async def test_unknown_skill_404(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = None
        with pytest.raises(NotFoundError):
            await service.install_skill(1, "no-such-skill")

    async def test_unpublished_others_custom_404(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = _custom(owner_user_id=2)
        with pytest.raises(NotFoundError):
            await service.install_skill(1, "my-skill")

    async def test_unpublished_own_custom_installable(
        self, service: SkillService
    ) -> None:
        service.skills.get_by_skill_id.return_value = _custom(owner_user_id=1)
        service.installs.get_install.return_value = None
        result = await service.install_skill(1, "my-skill")
        assert result.installed is True
        service.session.commit.assert_awaited_once()

    async def test_already_installed_409(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = _builtin()
        service.installs.get_install.return_value = _install(1, "market-daily-review")
        with pytest.raises(ConflictError):
            await service.install_skill(1, "market-daily-review")
        service.session.commit.assert_not_awaited()

    async def test_uninstall_not_installed_404(self, service: SkillService) -> None:
        service.installs.get_install.return_value = None
        with pytest.raises(NotFoundError):
            await service.uninstall_skill(1, "market-daily-review")

    async def test_uninstall_success(self, service: SkillService) -> None:
        install = _install(1, "market-daily-review", enabled=False)
        service.installs.get_install.return_value = install
        result = await service.uninstall_skill(1, "market-daily-review")
        assert result.installed is False
        service.installs.delete.assert_awaited_once_with(install)
        service.session.commit.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestCustomSkillCrud:
    def _payload(self, skill_id: str = "my-skill") -> CustomSkillCreateRequest:
        return CustomSkillCreateRequest(
            skill_id=skill_id,
            label="自定义",
            description="desc",
            custom_definition=CustomSkillDefinition(
                skill_md="# 方法论", system_prompt="你是……"
            ),
        )

    async def test_create_reserved_builtin_id_409(self, service: SkillService) -> None:
        with pytest.raises(ConflictError):
            await service.create_custom_skill(1, self._payload("market-daily-review"))
        service.skills.get_by_skill_id.assert_not_awaited()

    async def test_create_duplicate_id_409(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = _custom()
        with pytest.raises(ConflictError):
            await service.create_custom_skill(1, self._payload())
        service.session.commit.assert_not_awaited()

    async def test_create_draft_unpublished(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = None
        result = await service.create_custom_skill(1, self._payload())
        assert result.is_builtin is False
        assert result.published is False
        added = service.session.add.call_args[0][0]
        assert added.custom_definition["schema_version"] == 1
        service.session.commit.assert_awaited_once()

    async def test_update_others_custom_404(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = _custom(owner_user_id=2)
        with pytest.raises(NotFoundError):
            await service.update_custom_skill(1, "my-skill", MagicMock())

    async def test_update_builtin_404(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = _builtin()
        with pytest.raises(NotFoundError):
            await service.update_custom_skill(1, "market-daily-review", MagicMock())

    async def test_update_own_bumps_version(self, service: SkillService) -> None:
        row = _custom(owner_user_id=1)
        row.version = 1
        service.skills.get_by_skill_id.return_value = row
        from app.schemas.skill import CustomSkillUpdateRequest

        payload = CustomSkillUpdateRequest(label="改名")
        result = await service.update_custom_skill(1, "my-skill", payload)
        assert result.label == "改名"
        assert row.version == 2

    async def test_publish_others_custom_404(self, service: SkillService) -> None:
        service.skills.get_by_skill_id.return_value = _custom(owner_user_id=2)
        with pytest.raises(NotFoundError):
            await service.publish_custom_skill(1, "my-skill")

    async def test_publish_idempotent(self, service: SkillService) -> None:
        row = _custom(owner_user_id=1, published=True)
        service.skills.get_by_skill_id.return_value = row
        result = await service.publish_custom_skill(1, "my-skill")
        assert result.published is True
        service.session.commit.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
class TestListSkills:
    async def test_grouping_available_and_mine(self, service: SkillService) -> None:
        builtin = _builtin()
        others_custom = _custom("other-skill", owner_user_id=2, published=True)
        own_custom = _custom("my-skill", owner_user_id=1, published=False)
        service.skills.list_published.return_value = [builtin, others_custom, own_custom]
        service.skills.list_by_owner.return_value = [own_custom]
        service.installs.list_installed.return_value = [
            _install(1, "market-daily-review"),
            _install(1, "other-skill", enabled=False),
        ]

        result = await service.list_skills(1)

        available_ids = [item.skill_id for item in result.available]
        assert available_ids == ["market-daily-review", "other-skill"]

        mine_by_id = {item.skill_id: item for item in result.mine}
        assert set(mine_by_id) == {
            "market-daily-review",
            "other-skill",
            "my-skill",
        }
        assert mine_by_id["market-daily-review"].installed is True
        assert mine_by_id["market-daily-review"].enabled is True
        assert mine_by_id["other-skill"].enabled is False
        assert mine_by_id["my-skill"].installed is False

        available_by_id = {item.skill_id: item for item in result.available}
        assert available_by_id["market-daily-review"].installed is True

    async def test_installed_unknown_skill_row_skipped(
        self, service: SkillService
    ) -> None:
        service.skills.list_published.return_value = []
        service.skills.list_by_owner.return_value = []
        service.installs.list_installed.return_value = [_install(1, "ghost")]
        service.skills.get_by_skill_id.return_value = None
        result = await service.list_skills(1)
        assert result.mine == []
