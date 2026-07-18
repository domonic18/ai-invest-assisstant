"""Repository layer for data access.

Repositories encapsulate SQLAlchemy query logic. They do not manage
transactions; services own the transaction boundary.
"""

from app.repositories.base import BaseRepository
from app.repositories.collector_channel_config_repository import (
    CollectorChannelConfigRepository,
)
from app.repositories.collector_log_repository import CollectorLogRepository
from app.repositories.collector_task_repository import CollectorTaskRepository
from app.repositories.file_metadata_repository import FileMetadataRepository
from app.repositories.llm_config_repository import LLMConfigRepository
from app.repositories.news_announcement_repository import NewsAnnouncementRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.user_repository import UserRepository
from app.repositories.watchlist_repository import WatchlistRepository

__all__ = [
    "BaseRepository",
    "CollectorChannelConfigRepository",
    "CollectorLogRepository",
    "CollectorTaskRepository",
    "FileMetadataRepository",
    "LLMConfigRepository",
    "NewsAnnouncementRepository",
    "StockRepository",
    "UserRepository",
    "WatchlistRepository",
]
