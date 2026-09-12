"""问财 AI 选股直查 API 路由。

问财是秒级数据网关（实测 0.9~2.3s），非分钟级 LLM 生成，故允许阻塞式端点；
结果零落库。对话式筛选仍走 ``screen_stocks`` 工具 + page_event 范式。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.screening import ScreeningQueryRequest, ScreeningQueryResponse
from app.services.market import iwencai_service
from app.services.market.iwencai_service import IwencaiError

router = APIRouter()


@router.post("/query", response_model=ScreeningQueryResponse)
async def query_screening(
    body: ScreeningQueryRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> ScreeningQueryResponse:
    """问财即席选股直查（登录用户；结果为临时内容，不落库）。"""
    try:
        result = await iwencai_service.screen(body.query, limit=body.limit)
    except IwencaiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScreeningQueryResponse(
        query=result["query"],
        total=result["total"],
        truncated=result["truncated"],
        columns=result["columns"],
        stocks=result["stocks"],
    )
