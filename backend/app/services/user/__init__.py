"""User 域服务：用户、自选股、自选股行情。"""

from app.services.user import user_service, watchlist_quote_service, watchlist_service
from app.services.user.user_service import UserService
from app.services.user.watchlist_service import WatchlistService

__all__ = [
    "UserService",
    "WatchlistService",
    "user_service",
    "watchlist_quote_service",
    "watchlist_service",
]
