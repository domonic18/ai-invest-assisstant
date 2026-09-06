"""显式管理员引导：把指定用户名提权为 ``admin``。

注册不再自动授予首个账号 admin（防开放注册抢占提权），新部署先经页面注册
账号，再在应用容器内执行一次：

    docker compose exec web python -m app.cli.bootstrap_admin <username>
"""

import asyncio
import sys

import structlog
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User

logger = structlog.get_logger(__name__)


async def promote(username: str) -> bool:
    """将用户提权为 admin；用户不存在时返回 False。"""
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if user is None:
            logger.error("bootstrap_admin_user_not_found", username=username)
            return False
        if user.role == "admin":
            logger.info("bootstrap_admin_already", username=username)
            return True
        user.role = "admin"
        await session.commit()
        logger.info("bootstrap_admin_promoted", username=username, user_id=user.id)
        return True


def main() -> None:
    if len(sys.argv) != 2:
        print("用法: python -m app.cli.bootstrap_admin <username>", file=sys.stderr)
        sys.exit(2)
    ok = asyncio.run(promote(sys.argv[1]))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
