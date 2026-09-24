"""用量查询：个人配额/明细视图 + 管理端看板聚合（arch/10 §7）。

看板统计周期按北京时间（Asia/Shanghai）聚合，时间戳 aware UTC。
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import CN_TZ, utc_now
from app.models.account_quota import UserAiQuota, UserTokenUsage
from app.models.user import User
from app.services.quota.constants import OUTLET_SYSTEM

_CN_BUCKET = "(created_at AT TIME ZONE 'Asia/Shanghai')::date"
# join 了 "user" 表后 created_at 产生歧义，须用表名限定
_CN_BUCKET_QUALIFIED = "(user_token_usage.created_at AT TIME ZONE 'Asia/Shanghai')::date"


def cn_bucket_day(moment: datetime) -> date:
    """时间戳所属的北京时间日历日（上方 SQL 日分桶的 Python 口径，测试据此对齐）。"""
    return moment.astimezone(CN_TZ).date()


async def get_quota_view(session: AsyncSession, user: User) -> dict[str, Any]:
    """个人配额视图：总量 / 已用（仅系统出口）/ 剩余 / 是否不限 / 是否 BYOK。"""
    from app.services.quota import account_settings

    quota = await session.get(UserAiQuota, user.id)
    total = quota.total_tokens if quota is not None else 0
    unlimited = total is None or (
        user.role == "admin" and await account_settings.get_admin_exempt(session)
    )
    used = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(UserTokenUsage.total_tokens), 0)).where(
                    UserTokenUsage.user_id == user.id,
                    UserTokenUsage.outlet == OUTLET_SYSTEM,
                )
            )
        ).scalar_one()
    )
    return {
        "total_tokens": total,
        "used_tokens": used,
        "remaining_tokens": None if unlimited else int(total or 0) - used,
        "unlimited": unlimited,
        "byok_enabled": await _has_byok_row(session, user.id),
    }


async def _has_byok_row(session: AsyncSession, user_id: int) -> bool:
    from app.models.account_quota import UserLlmConfig

    # user_id 是 UNIQUE 列非主键，session.get 会按 id 误配他人行
    row = await session.scalar(
        select(UserLlmConfig.id).where(UserLlmConfig.user_id == user_id).limit(1)
    )
    return row is not None


async def list_usage(
    session: AsyncSession,
    user_id: int,
    *,
    feature: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """个人消耗明细（新在前）+ 按功能分组汇总。"""
    stmt = select(UserTokenUsage).where(UserTokenUsage.user_id == user_id)
    if feature:
        stmt = stmt.where(UserTokenUsage.feature == feature)
    items = (
        (await session.execute(stmt.order_by(UserTokenUsage.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    summary_rows = (
        await session.execute(
            select(
                UserTokenUsage.feature,
                func.sum(UserTokenUsage.total_tokens),
                func.count(),
            )
            .where(UserTokenUsage.user_id == user_id)
            .group_by(UserTokenUsage.feature)
        )
    ).all()
    return {
        "items": [
            {
                "feature": row.feature,
                "model_name": row.model_name,
                "outlet": row.outlet,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "estimated": row.estimated,
                "created_at": row.created_at,
            }
            for row in items
        ],
        "by_feature": {row[0]: int(row[1]) for row in summary_rows},
    }


async def dashboard(session: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """管理端用量看板聚合（北京时间日分桶）。"""
    since: datetime = utc_now() - timedelta(days=days)

    bucket: ColumnElement[Any] = literal_column(_CN_BUCKET).label("bucket")
    trend = (
        await session.execute(
            select(
                func.to_char(bucket, "YYYY-MM-DD").label("d"),
                func.sum(UserTokenUsage.total_tokens).label("tokens"),
            )
            .where(UserTokenUsage.created_at >= since)
            .group_by(bucket)
            .order_by(bucket)
        )
    ).all()

    by_feature = (
        await session.execute(
            select(
                UserTokenUsage.feature,
                func.sum(UserTokenUsage.total_tokens),
                func.count(),
            )
            .where(UserTokenUsage.created_at >= since)
            .group_by(UserTokenUsage.feature)
        )
    ).all()

    by_model = (
        await session.execute(
            select(
                UserTokenUsage.model_name,
                func.sum(UserTokenUsage.total_tokens),
            )
            .where(UserTokenUsage.created_at >= since)
            .group_by(UserTokenUsage.model_name)
        )
    ).all()

    top_users = (
        await session.execute(
            select(
                UserTokenUsage.user_id,
                User.username,
                func.sum(UserTokenUsage.total_tokens),
            )
            .outerjoin(User, User.id == UserTokenUsage.user_id)
            .where(UserTokenUsage.created_at >= since, UserTokenUsage.user_id.isnot(None))
            .group_by(UserTokenUsage.user_id, User.username)
            .order_by(func.sum(UserTokenUsage.total_tokens).desc())
            .limit(10)
        )
    ).all()

    estimated_row = (
        await session.execute(
            select(
                func.sum(case((UserTokenUsage.estimated, 1), else_=0)),
                func.count(),
            ).where(UserTokenUsage.created_at >= since)
        )
    ).one()

    # 配额耗尽用户数：有限额且系统出口累计 ≥ 总量
    used_expr = (
        select(
            UserTokenUsage.user_id,
            func.sum(UserTokenUsage.total_tokens).label("used"),
        )
        .where(UserTokenUsage.outlet == OUTLET_SYSTEM)
        .group_by(UserTokenUsage.user_id)
        .subquery()
    )
    exhausted = (
        await session.execute(
            select(func.count())
            .select_from(UserAiQuota)
            .outerjoin(used_expr, used_expr.c.user_id == UserAiQuota.user_id)
            .where(
                UserAiQuota.total_tokens.isnot(None),
                func.coalesce(used_expr.c.used, 0) >= UserAiQuota.total_tokens,
            )
        )
    ).scalar_one()

    total_calls = int(estimated_row[1] or 0)
    return {
        "since": since,
        "days": days,
        "trend_daily": [{"date": row[0], "total_tokens": int(row[1])} for row in trend],
        "by_feature": {row[0]: int(row[1]) for row in by_feature},
        "by_model": {row[0]: int(row[1]) for row in by_model},
        "top_users": [
            {"user_id": row[0], "username": row[1], "total_tokens": int(row[2])}
            for row in top_users
        ],
        "estimated_ratio": (int(estimated_row[0] or 0) / total_calls) if total_calls else 0.0,
        "exhausted_users": int(exhausted or 0),
    }


async def per_user_usage(session: AsyncSession, *, days: int = 30) -> list[dict[str, Any]]:
    """按用户聚合的消耗明细（对齐大模型平台用量页）：总量/调用次数/最近使用/日趋势。

    日趋势按北京时间分桶，前端以迷你柱状与行展开明细呈现。
    """
    since: datetime = utc_now() - timedelta(days=days)
    bucket: ColumnElement[Any] = literal_column(_CN_BUCKET_QUALIFIED).label("bucket")

    rows = (
        await session.execute(
            select(
                UserTokenUsage.user_id,
                User.username,
                func.sum(UserTokenUsage.total_tokens),
                func.count(),
                func.max(UserTokenUsage.created_at),
                func.to_char(bucket, "YYYY-MM-DD"),
                func.sum(UserTokenUsage.total_tokens).label("daily_tokens"),
            )
            .outerjoin(User, User.id == UserTokenUsage.user_id)
            .where(UserTokenUsage.created_at >= since, UserTokenUsage.user_id.isnot(None))
            .group_by(
                UserTokenUsage.user_id, User.username, bucket
            )
            .order_by(UserTokenUsage.user_id)
        )
    ).all()

    users: dict[int, dict[str, Any]] = {}
    for row in rows:
        user_id = int(row[0])
        entry = users.setdefault(
            user_id,
            {
                "user_id": user_id,
                "username": row[1],
                "total_tokens": 0,
                "calls": 0,
                "last_used_at": None,
                "daily": [],
            },
        )
        entry["total_tokens"] += int(row[2])
        entry["calls"] += int(row[3])
        last_used = row[4]
        if last_used is not None and (
            entry["last_used_at"] is None or last_used > entry["last_used_at"]
        ):
            entry["last_used_at"] = last_used
        entry["daily"].append({"date": row[5], "total_tokens": int(row[6])})

    result = sorted(users.values(), key=lambda item: -item["total_tokens"])
    for entry in result:
        entry["daily"].sort(key=lambda point: point["date"])
    return result
