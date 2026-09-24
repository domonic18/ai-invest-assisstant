"""个人账号治理端点：我的配额 / 消耗明细 / 我的模型（BYOK）。

挂在 ``/users/me/*`` 命名空间（api/v1 聚合处以 ``prefix="/users"`` 挂载），
全部登录态、仅本人可访问。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.account import (
    LlmConnectionTestResponse,
    QuotaResponse,
    UsageResponse,
    UserLlmConfigResponse,
    UserLlmConfigUpsertRequest,
)
from app.services.quota.usage_query_service import (
    get_quota_view,
    list_usage,
)
from app.services.quota.user_llm_service import (
    clear_user_llm_config,
    get_user_llm_config,
    save_user_llm_config,
    test_user_llm_connection,
)

router = APIRouter()


@router.get("/me/quota", response_model=QuotaResponse)
async def get_my_quota(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> QuotaResponse:
    """我的配额：总量 / 已用 / 剩余 / 是否不限 / 是否已配自备 Key。"""
    view = await get_quota_view(session, user)
    return QuotaResponse.model_validate(view)


@router.get("/me/usage", response_model=UsageResponse)
async def get_my_usage(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    feature: str | None = Query(None, pattern="^(assistant|page|api_key|system)$"),
    limit: int = Query(50, ge=1, le=200),
) -> UsageResponse:
    """我的消耗明细（按功能过滤）+ 分组汇总。"""
    data = await list_usage(session, user.id, feature=feature, limit=limit)
    return UsageResponse.model_validate(data)


@router.get("/me/llm-config", response_model=UserLlmConfigResponse)
async def get_my_llm_config(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserLlmConfigResponse:
    """我的模型配置（脱敏视图；404 = 未配置）。"""
    from app.core.exceptions import NotFoundError

    view = await get_user_llm_config(session, user.id)
    if view is None:
        raise NotFoundError("尚未配置自备模型")
    return UserLlmConfigResponse(
        protocol=view.protocol,
        base_url=view.base_url,
        model_name=view.model_name,
        api_key_masked=view.api_key_masked,
    )


@router.put("/me/llm-config", response_model=UserLlmConfigResponse)
async def save_my_llm_config(
    data: UserLlmConfigUpsertRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> UserLlmConfigResponse:
    """保存自备模型配置：此后本人 AI 全走自有 Key（不占配额、失败不回退）。"""
    view = await save_user_llm_config(
        session,
        user.id,
        protocol=data.protocol,
        base_url=data.base_url,
        model_name=data.model_name,
        api_key=data.api_key,
    )
    return UserLlmConfigResponse(
        protocol=view.protocol,
        base_url=view.base_url,
        model_name=view.model_name,
        api_key_masked=view.api_key_masked,
    )


@router.delete("/me/llm-config", status_code=status.HTTP_204_NO_CONTENT)
async def clear_my_llm_config(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """清除自备模型配置，立即回落系统模型（此后受配额约束）。"""
    from app.core.exceptions import NotFoundError

    if not await clear_user_llm_config(session, user.id):
        raise NotFoundError("尚未配置自备模型")


@router.post("/me/llm-config/test", response_model=LlmConnectionTestResponse)
async def test_my_llm_config(
    data: UserLlmConfigUpsertRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> LlmConnectionTestResponse:
    """草稿参数连通性测试（不落库）。"""
    test_status, detail = await test_user_llm_connection(
        protocol=data.protocol,
        base_url=data.base_url,
        model_name=data.model_name,
        api_key=data.api_key,
    )
    return LlmConnectionTestResponse(status=test_status, detail=detail)
