from fastapi import APIRouter

from app.api.v1 import (
    assistant,
    auction,
    auth,
    chain,
    financial,
    financial_report,
    fund_flow,
    hotspot,
    kline,
    market,
    research,
    stocks,
    users,
)
from app.api.v1.admin import collector as admin_collector
from app.api.v1.admin import collector_channels as admin_collector_channels
from app.api.v1.admin import collector_data_types as admin_collector_data_types
from app.api.v1.admin import llm_config as admin_llm_configs
from app.api.v1.admin import news as admin_news
from app.api.v1.admin import reports as admin_reports
from app.api.v1.admin import stocks as admin_stocks
from app.api.v1.admin import system as admin_system
from app.api.v1.admin import tasks as admin_tasks
from app.api.v1.admin import users as admin_users
from app.api.v1.mcp import server as mcp_server

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(kline.router, prefix="/kline", tags=["kline"])
api_router.include_router(chain.router, prefix="/chain", tags=["chain"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(
    financial_report.router, prefix="/financial-reports", tags=["financial-reports"]
)
api_router.include_router(hotspot.router, prefix="/hotspot", tags=["hotspot"])
api_router.include_router(financial.router, prefix="/financial", tags=["financial"])
api_router.include_router(auction.router, prefix="/auction", tags=["auction"])
api_router.include_router(fund_flow.router, prefix="/fund-flow", tags=["fund-flow"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(
    assistant.router, prefix="/assistant", tags=["assistant"]
)

admin_router = APIRouter(prefix="/admin", tags=["admin"])
admin_router.include_router(admin_users.router, prefix="/users")
admin_router.include_router(admin_stocks.router, prefix="/stocks")
admin_router.include_router(admin_reports.router, prefix="/reports")
admin_router.include_router(admin_news.router, prefix="/news")
admin_router.include_router(admin_tasks.router, prefix="/tasks")
admin_router.include_router(admin_system.router, prefix="/system")
admin_router.include_router(admin_collector.router)
admin_router.include_router(admin_collector_data_types.router)
admin_router.include_router(admin_collector_channels.router)
admin_router.include_router(admin_llm_configs.router)
api_router.include_router(admin_router)

api_router.include_router(mcp_server.router, prefix="/mcp", tags=["mcp"])
