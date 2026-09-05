"""Pydantic schemas 模块。"""

from app.schemas.auth import AuthResponse, RegisterRequest, TokenPayload
from app.schemas.capital_fund_flow_sector import (
    HotspotListRequest,
    SectorFundFlowResponse,
)
from app.schemas.chain import (
    ChainAlertItem,
    ChainAlertResponse,
    ChainAnalysisRequest,
    ChainAnalysisResult,
    ChainCompany,
    ChainEdge,
    ChainNode,
)
from app.schemas.collector_channel_config import (
    CollectorChannelConfigCreate,
    CollectorChannelConfigResponse,
    CollectorChannelConfigUpdate,
)
from app.schemas.collector_task import (
    CollectorTaskCreate,
    CollectorTaskResponse,
    CollectorTaskUpdate,
)
from app.schemas.file_metadata import (
    FileMetadataCreate,
    FileMetadataResponse,
    FileMetadataUpdate,
)
from app.schemas.financial import (
    FinancialHealthRequest,
    FinancialHealthResponse,
)
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)
from app.schemas.news_announcement import (
    NewsAnnouncementResponse,
    ResearchReportDetailResponse,
    ResearchReportListRequest,
    ResearchReportResponse,
)
from app.schemas.stock import (
    AdminStockCreate,
    AdminStockUpdate,
    AuctionDataResponse,
    FundFlowResponse,
    KlineDataResponse,
    PaginatedResponse,
    PaginationParams,
    StockAiAnalysisResponse,
    StockAiAnalysisSection,
    StockBasicResponse,
    StockSearchRequest,
)
from app.schemas.user import (
    AdminUserCreate,
    AdminUserResetPassword,
    AdminUserUpdate,
    UserResponse,
    WatchlistGroupCreate,
    WatchlistGroupReorderRequest,
    WatchlistGroupResponse,
    WatchlistGroupUpdate,
    WatchlistGroupWithItemsResponse,
    WatchlistItemCreate,
    WatchlistItemMoveRequest,
    WatchlistItemResponse,
)

__all__ = [
    "AuthResponse",
    "RegisterRequest",
    "TokenPayload",
    "UserResponse",
    "WatchlistGroupCreate",
    "WatchlistGroupReorderRequest",
    "WatchlistGroupResponse",
    "WatchlistGroupUpdate",
    "WatchlistGroupWithItemsResponse",
    "WatchlistItemCreate",
    "WatchlistItemMoveRequest",
    "WatchlistItemResponse",
    "AdminUserCreate",
    "AdminUserUpdate",
    "AdminUserResetPassword",
    "StockBasicResponse",
    "StockSearchRequest",
    "StockAiAnalysisResponse",
    "StockAiAnalysisSection",
    "AdminStockCreate",
    "AdminStockUpdate",
    "KlineDataResponse",
    "AuctionDataResponse",
    "FundFlowResponse",
    "PaginationParams",
    "PaginatedResponse",
    "ChainAlertItem",
    "ChainAlertResponse",
    "ChainAnalysisRequest",
    "ChainAnalysisResult",
    "ChainCompany",
    "ChainEdge",
    "ChainNode",
    "CollectorChannelConfigCreate",
    "CollectorChannelConfigUpdate",
    "CollectorChannelConfigResponse",
    "LLMConfigCreate",
    "LLMConfigUpdate",
    "LLMConfigResponse",
    "LLMConfigTestResponse",
    "NewsAnnouncementResponse",
    "ResearchReportResponse",
    "ResearchReportDetailResponse",
    "ResearchReportListRequest",
    "SectorFundFlowResponse",
    "HotspotListRequest",
    "FinancialHealthResponse",
    "FinancialHealthRequest",
    "FileMetadataCreate",
    "FileMetadataUpdate",
    "FileMetadataResponse",
    "CollectorTaskCreate",
    "CollectorTaskUpdate",
    "CollectorTaskResponse",
]
