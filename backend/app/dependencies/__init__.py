"""FastAPI 依赖项：认证、数据库会话与 AI 配额闸门。"""

from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.quota import quota_service
from app.services.quota.constants import UsageFeature
from app.services.quota.context import meter_scope

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话。

    事务边界由服务层/调用方控制：本依赖只负责提供会话并在异常时回滚，
    不做自动提交。写操作必须由服务层显式 ``session.commit()``。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """通过 JWT 获取当前用户（校验启用与审批状态）。"""
    credentials_exception = UnauthorizedError("Could not validate credentials")

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await session.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    # 审批状态拦截（防御纵深：审批前无凭证，覆盖后续状态回退，arch/10 §6.2）
    if user.status != "approved":
        if user.status == "pending":
            raise UnauthorizedError("账号待审批，请等待管理员开通")
        if user.status == "rejected":
            raise UnauthorizedError("注册申请未通过，请重新提交申请")

    return user


async def get_current_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """通过 JWT 获取当前管理员用户。"""
    if user.role != "admin":
        raise ForbiddenError("Admin access required")
    return user


def ai_quota_gate(feature: UsageFeature) -> Callable[..., AsyncIterator[User]]:
    """AI 入口依赖工厂：请求前配额预检（耗尽 429）+ 计量上下文包裹（arch/10 §3）。

    LangChain callback 内抛出的异常会被吞掉，配额拦截必须在入口显式执行；
    yield 依赖与端点在同一请求任务内执行，meter_scope 的 ContextVar 对端点可见。
    """

    async def gate(
        user: Annotated[User, Depends(get_current_user)],
    ) -> AsyncIterator[User]:
        await quota_service.precheck(user.id)
        with meter_scope(user.id, feature):
            yield user

    return gate
