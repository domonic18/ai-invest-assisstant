"""用户自选股与分组业务服务。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.watchlist import UserWatchlist, UserWatchlistGroup
from app.repositories.user.watchlist_group_repository import WatchlistGroupRepository
from app.repositories.user.watchlist_repository import WatchlistRepository
from app.schemas.user import WatchlistGroupCreate, WatchlistGroupUpdate, WatchlistItemCreate

DEFAULT_GROUP_NAME = "默认分组"
MAX_GROUPS_PER_USER = 20


class GroupLimitError(ValueError):
    """分组数量超出上限。"""


class WatchlistService:
    """用户自选股与分组业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WatchlistRepository(session)
        self.group_repo = WatchlistGroupRepository(session)

    # ------------------------------------------------------------------
    # 分组
    # ------------------------------------------------------------------

    async def get_or_create_default_group(self, user_id: int) -> UserWatchlistGroup:
        """获取默认分组，缺失时惰性创建（历史数据/新用户兜底）。"""
        group = await self.group_repo.get_default(user_id)
        if group is not None:
            return group
        group = UserWatchlistGroup(
            user_id=user_id,
            name=DEFAULT_GROUP_NAME,
            sort_order=0,
            is_default=True,
            ai_review_enabled=False,
        )
        self.group_repo.add(group)
        await self.session.commit()
        await self.group_repo.refresh(group)
        return group

    async def list_groups_with_items(self, user_id: int) -> list[UserWatchlistGroup]:
        """返回用户分组（含组内股票），确保默认分组存在。"""
        await self.get_or_create_default_group(user_id)
        return await self.group_repo.list_by_user(user_id)

    async def create_group(self, user_id: int, data: WatchlistGroupCreate) -> UserWatchlistGroup:
        """创建分组：重名拒绝，超出上限拒绝。"""
        if await self.group_repo.count_by_user(user_id) >= MAX_GROUPS_PER_USER:
            raise GroupLimitError(f"Group limit reached ({MAX_GROUPS_PER_USER})")
        if await self.group_repo.get_by_name(user_id, data.name) is not None:
            raise ValueError("Group name already exists")
        groups = await self.group_repo.list_by_user(user_id)
        sort_order = groups[-1].sort_order + 1 if groups else 0
        group = UserWatchlistGroup(
            user_id=user_id,
            name=data.name,
            sort_order=sort_order,
            is_default=False,
            ai_review_enabled=data.ai_review_enabled,
        )
        self.group_repo.add(group)
        await self.session.commit()
        await self.group_repo.refresh(group)
        return group

    async def update_group(
        self, user_id: int, group_id: int, data: WatchlistGroupUpdate
    ) -> UserWatchlistGroup:
        """更新分组名称/AI 复盘开关；默认分组禁止改名。"""
        group = await self._get_owned_group(user_id, group_id)
        if data.name is not None and data.name != group.name:
            if group.is_default:
                raise ValueError("Default group cannot be renamed")
            if await self.group_repo.get_by_name(user_id, data.name) is not None:
                raise ValueError("Group name already exists")
            group.name = data.name
        if data.ai_review_enabled is not None:
            group.ai_review_enabled = data.ai_review_enabled
        await self.session.commit()
        await self.group_repo.refresh(group)
        return group

    async def delete_group(self, user_id: int, group_id: int) -> None:
        """删除分组：默认分组拒绝，组内股票移入默认分组。"""
        group = await self._get_owned_group(user_id, group_id)
        if group.is_default:
            raise ValueError("Default group cannot be deleted")
        default = await self.get_or_create_default_group(user_id)
        if group.id == default.id:  # 理论不可达，防御越权构造
            raise ValueError("Default group cannot be deleted")
        for item in group.items:
            item.group_id = default.id
        await self.session.delete(group)
        await self.session.commit()

    async def reorder_groups(self, user_id: int, group_ids: list[int]) -> None:
        """按传入顺序重排分组（必须覆盖该用户全部分组）。"""
        groups = await self.group_repo.list_by_user(user_id)
        by_id = {g.id: g for g in groups}
        if sorted(group_ids) != sorted(by_id):
            raise ValueError("Group id list does not match user groups")
        for idx, group_id in enumerate(group_ids):
            by_id[group_id].sort_order = idx
        await self.session.commit()

    async def _get_owned_group(self, user_id: int, group_id: int) -> UserWatchlistGroup:
        """获取属于指定用户的分组，否则视为不存在。"""
        group = await self.group_repo.get_by_user_and_id(user_id, group_id)
        if group is None:
            raise LookupError("Group not found")
        return group

    # ------------------------------------------------------------------
    # 自选股
    # ------------------------------------------------------------------

    async def get_watchlist_by_user(self, user_id: int) -> list[UserWatchlist]:
        """获取用户自选股列表。"""
        return await self.repo.list_by_user(user_id)

    async def add_watchlist_item(
        self, user: User, data: WatchlistItemCreate
    ) -> UserWatchlist:
        """添加自选股（group_id 缺省挂默认分组）。"""
        existing = await self.repo.get_by_user_and_stock(user.id, data.stock_code)
        if existing:
            raise ValueError("Stock already in watchlist")

        if data.group_id is not None:
            group = await self.group_repo.get_by_user_and_id(user.id, data.group_id)
            if group is None:
                raise ValueError("Group not found")
        else:
            group = await self.get_or_create_default_group(user.id)

        item = UserWatchlist(
            user_id=user.id,
            stock_code=data.stock_code,
            tags=data.tags,
            group_id=group.id,
        )
        self.repo.add(item)
        await self.session.commit()
        await self.repo.refresh(item)
        return item

    async def move_watchlist_item(
        self, user_id: int, item_id: int, target_group_id: int
    ) -> UserWatchlist:
        """移动自选股到目标分组。"""
        item = await self._get_owned_item(user_id, item_id)
        target = await self.group_repo.get_by_user_and_id(user_id, target_group_id)
        if target is None:
            raise ValueError("Target group not found")
        if item.group_id == target_group_id:
            return item
        item.group_id = target_group_id
        await self.session.commit()
        await self.repo.refresh(item)
        return item

    async def remove_watchlist_item(self, user_id: int, item_id: int) -> None:
        """删除自选股。"""
        item = await self._get_owned_item(user_id, item_id)
        await self.session.delete(item)
        await self.session.commit()

    async def _get_owned_item(self, user_id: int, item_id: int) -> UserWatchlist:
        """获取属于指定用户的自选股，否则视为不存在。"""
        item = await self.session.get(UserWatchlist, item_id)
        if item is None or item.user_id != user_id:
            raise LookupError("Watchlist item not found")
        return item
