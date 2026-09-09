"""技能广场端点契约测试（鉴权 / 状态码 / camelCase wire）。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.dependencies import get_current_user
from app.main import app
from app.schemas.skill import (
    CustomSkillDefinition,
    SkillFile,
    SkillFilesResponse,
    SkillItem,
    SkillResponse,
    SkillSquareResponse,
    UserSkillResponse,
)

_NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


@pytest.fixture
def user():
    return type(
        "User",
        (object,),
        {"id": 1, "username": "user", "role": "user", "is_active": True},
    )()


@pytest.fixture
def auth_client(client, user):
    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.clear()


def _skill_response(skill_id: str = "my-skill", published: bool = False) -> SkillResponse:
    return SkillResponse(
        skill_id=skill_id,
        label="自定义",
        kind="custom",
        is_builtin=False,
        published=published,
        description="描述",
        owner_user_id=1,
        version=1,
        custom_definition={"skill_md": "s", "system_prompt": "p", "schema_version": 1},
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.mark.unit
class TestSkillsApi:
    def test_list_skills_groups(self, auth_client) -> None:
        payload = SkillSquareResponse(
            available=[
                SkillItem(
                    skill_id="market-daily-review",
                    label="大盘每日复盘",
                    kind="executable",
                    is_builtin=True,
                    published=True,
                    installed=True,
                    enabled=True,
                )
            ],
            mine=[
                SkillItem(
                    skill_id="my-skill",
                    label="自定义",
                    kind="custom",
                    is_builtin=False,
                    published=False,
                )
            ],
        )
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.list_skills = AsyncMock(return_value=payload)
            resp = auth_client.get("/api/v1/skills")

        assert resp.status_code == 200
        body = resp.json()
        assert body["available"][0]["skillId"] == "market-daily-review"
        assert body["available"][0]["isBuiltin"] is True
        assert body["mine"][0]["kind"] == "custom"

    def test_create_custom_skill_201(self, auth_client) -> None:
        created = _skill_response()
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.create_custom_skill = AsyncMock(
                return_value=created
            )
            resp = auth_client.post(
                "/api/v1/skills",
                json={
                    "skillId": "my-skill",
                    "label": "自定义",
                    "customDefinition": {
                        "skillMd": "# 方法论",
                        "systemPrompt": "你是……",
                    },
                },
            )

        assert resp.status_code == 201
        assert resp.json()["skillId"] == "my-skill"
        call = service_cls.return_value.create_custom_skill.call_args
        assert call.args[1].skill_id == "my-skill"
        assert call.args[1].custom_definition.system_prompt == "你是……"

    def test_create_custom_skill_conflict_409(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.create_custom_skill = AsyncMock(
                side_effect=ConflictError("skill_id 已存在: my-skill")
            )
            resp = auth_client.post(
                "/api/v1/skills",
                json={
                    "skillId": "my-skill",
                    "label": "自定义",
                    "customDefinition": {
                        "skillMd": "# 方法论",
                        "systemPrompt": "你是……",
                    },
                },
            )

        assert resp.status_code == 409
        assert "已存在" in resp.json()["detail"]

    def test_get_skill_detail_200(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.get_skill_detail = AsyncMock(
                return_value=_skill_response()
            )
            resp = auth_client.get("/api/v1/skills/my-skill")

        assert resp.status_code == 200
        assert resp.json()["customDefinition"]["systemPrompt"] == "p"
        assert resp.json()["customDefinition"]["skillMd"] == "s"

    def test_get_skill_detail_404(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.get_skill_detail = AsyncMock(
                side_effect=NotFoundError("技能不存在")
            )
            resp = auth_client.get("/api/v1/skills/ghost")

        assert resp.status_code == 404

    def test_update_custom_skill_200(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.update_custom_skill = AsyncMock(
                return_value=_skill_response()
            )
            resp = auth_client.patch(
                "/api/v1/skills/my-skill", json={"label": "改名"}
            )

        assert resp.status_code == 200
        service_cls.return_value.update_custom_skill.assert_awaited_once()

    def test_publish_custom_skill_200(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.publish_custom_skill = AsyncMock(
                return_value=_skill_response(published=True)
            )
            resp = auth_client.post("/api/v1/skills/my-skill/publish")

        assert resp.status_code == 200
        assert resp.json()["published"] is True

    def test_install_skill_201(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.install_skill = AsyncMock(
                return_value=UserSkillResponse(
                    skill_id="market-daily-review", installed=True, enabled=True
                )
            )
            resp = auth_client.post("/api/v1/skills/market-daily-review/install")

        assert resp.status_code == 201
        assert resp.json()["installed"] is True

    def test_install_skill_conflict_409(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.install_skill = AsyncMock(
                side_effect=ConflictError("技能已安装")
            )
            resp = auth_client.post("/api/v1/skills/market-daily-review/install")

        assert resp.status_code == 409

    def test_uninstall_skill_204(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.uninstall_skill = AsyncMock(
                return_value=UserSkillResponse(
                    skill_id="market-daily-review",
                    installed=False,
                    enabled=True,
                )
            )
            resp = auth_client.delete("/api/v1/skills/market-daily-review/install")

        assert resp.status_code == 204

    def test_uninstall_skill_404(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.uninstall_skill = AsyncMock(
                side_effect=NotFoundError("技能未安装")
            )
            resp = auth_client.delete("/api/v1/skills/ghost/install")

        assert resp.status_code == 404

    def test_custom_definition_sections_wire(self, auth_client) -> None:
        """sections 定义经 camelCase wire 往返不丢字段。"""
        definition = CustomSkillDefinition(
            skill_md="# 方法论",
            system_prompt="你是……",
            sections=[{"key": "logic", "title": "逻辑", "requirements": "必填"}],
        )
        payload = {
            "skillId": "my-skill",
            "label": "自定义",
            "customDefinition": definition.model_dump(by_alias=True),
        }
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.create_custom_skill = AsyncMock(
                return_value=_skill_response()
            )
            resp = auth_client.post("/api/v1/skills", json=payload)

        assert resp.status_code == 201
        call = service_cls.return_value.create_custom_skill.call_args
        assert call.args[1].custom_definition.sections[0].key == "logic"

    def test_get_skill_files(self, auth_client) -> None:
        payload = SkillFilesResponse(
            skill_id="market-daily-review",
            is_builtin=True,
            synthetic=False,
            files=[
                SkillFile(path="SKILL.md", size=11, content="# 大盘每日复盘"),
                SkillFile(path="prompt.yaml", size=26, content="id: market-daily-review"),
            ],
        )
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.get_skill_files = AsyncMock(return_value=payload)
            resp = auth_client.get("/api/v1/skills/market-daily-review/files")

        assert resp.status_code == 200
        body = resp.json()
        assert body["skillId"] == "market-daily-review"
        assert body["isBuiltin"] is True
        assert body["synthetic"] is False
        assert [f["path"] for f in body["files"]] == ["SKILL.md", "prompt.yaml"]
        assert body["files"][0]["content"] == "# 大盘每日复盘"
        service_cls.return_value.get_skill_files.assert_awaited_once_with(
            1, "market-daily-review"
        )

    def test_get_skill_files_not_found_404(self, auth_client) -> None:
        with patch("app.api.v1.skills.SkillService") as service_cls:
            service_cls.return_value.get_skill_files = AsyncMock(
                side_effect=NotFoundError("技能不存在: ghost")
            )
            resp = auth_client.get("/api/v1/skills/ghost/files")

        assert resp.status_code == 404
