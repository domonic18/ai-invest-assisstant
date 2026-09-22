"""知识库消费侧 API（arch/12 §10.2）：权限 = admin 或 kb_settings 白名单。

E4：混合检索 + 发布态章节树导航 + 章节卡片清单（浏览路径）；
F1：播放凭证、视频代理流、书页水印位图、字幕轨（§8 防盗面唯一入口）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.kb import KbDocKind, KbPointType
from app.constants.pagination import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.exceptions import ForbiddenError
from app.dependencies import client_ip, get_current_user, get_db
from app.models.user import User
from app.schemas.kb import (
    KbChapterPointsResponse,
    KbConsumerSourceResponse,
    KbImageUrlResponse,
    KbPlaybackTokenResponse,
    KbPublishedChaptersResponse,
    KbSearchResponse,
)
from app.services.kb import (
    playback_service,
    search_service,
    settings_service,
    source_service,
)


async def get_kb_authorized_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """知识库消费权限：admin 或 authorized_user_ids 白名单（arch/12 §9）。"""
    if user.role != "admin":
        settings = await settings_service.get_settings_row(session)
        if user.id not in (settings.authorized_user_ids or []):
            raise ForbiddenError("知识库访问未授权")
    return user


router = APIRouter()


@router.get(
    "/sources",
    response_model=list[KbConsumerSourceResponse],
    dependencies=[Depends(get_kb_authorized_user)],
)
async def list_sources(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[KbConsumerSourceResponse]:
    """消费侧知识库列表（启用中最小投影；403 兼作消费页未授权提示）。"""
    return await source_service.list_consumer_sources(session)


@router.get(
    "/search", response_model=KbSearchResponse, dependencies=[Depends(get_kb_authorized_user)]
)
async def search(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(..., min_length=1, max_length=200),
    source_id: int | None = Query(default=None),
    chapter_path: str | None = Query(default=None, max_length=600),
    point_type: KbPointType | None = Query(default=None),
    kind: KbDocKind | None = Query(default=None),
) -> KbSearchResponse:
    """混合检索：BM25 + 向量双路 RRF 融合，三类命中独立列表。"""
    return await search_service.search(
        session,
        q=q,
        source_id=source_id,
        chapter_path=chapter_path.split(",") if chapter_path else None,
        point_type=point_type.value if point_type else None,
        kind=kind.value if kind else None,
    )


@router.get(
    "/sources/{source_id}/chapters",
    response_model=KbPublishedChaptersResponse,
    dependencies=[Depends(get_kb_authorized_user)],
)
async def get_chapters(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbPublishedChaptersResponse:
    """发布态章节树导航（消费侧不暴露 draft）。"""
    return await search_service.get_published_chapters(session, source_id)


@router.get(
    "/sources/{source_id}/points",
    response_model=KbChapterPointsResponse,
    dependencies=[Depends(get_kb_authorized_user)],
)
async def list_chapter_points(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    chapter_path: str = Query(..., max_length=600),
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> KbChapterPointsResponse:
    """章节卡片清单（浏览路径）：确定性排序分页，不依赖检索投影。"""
    return await search_service.list_chapter_points(
        session,
        source_id,
        chapter_path=[seg.strip() for seg in chapter_path.split(",") if seg.strip()],
        page=page,
        page_size=page_size,
    )


@router.post(
    "/media/{media_id}/playback-token", response_model=KbPlaybackTokenResponse
)
async def issue_playback_token(
    media_id: int,
    user: Annotated[User, Depends(get_kb_authorized_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbPlaybackTokenResponse:
    """一次性播放凭证（≤30min 绑定用户+素材；携带上/下一集 id）。"""
    return await playback_service.issue_playback_token(
        session, user_id=user.id, media_id=media_id
    )


@router.get("/stream/{media_id}")
async def stream_media(
    media_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(..., min_length=8, max_length=128),
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    """视频代理流：token + Range 必须，206 分段透传（无 COS 直链暴露）。

    凭证即鉴权（无 Bearer）：``<video>`` 元素 src 无法携带 Authorization
    header，短时效凭证绑定用户+素材即身份（arch/12 §8.1）。
    """
    stream = await playback_service.open_media_stream(
        session,
        media_id=media_id,
        token=token,
        range_header=range_header,
        ip=client_ip(request),
    )
    return StreamingResponse(
        stream.chunks,
        status_code=206,
        media_type=stream.content_type,
        headers={
            "Content-Range": f"bytes {stream.start}-{stream.end}/{stream.total}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(stream.end - stream.start + 1),
            "Cache-Control": "no-store",
        },
    )


@router.get("/books/{media_id}/pages/{page_no}")
async def get_book_page(
    media_id: int,
    page_no: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(..., min_length=8, max_length=128),
) -> Response:
    """书页位图：pypdfium2 渲染 + 服务端烧录「用户名+日期」水印。

    凭证即鉴权（无 Bearer）：``<img>`` 元素 src 无法携带 Authorization
    header，水印用户名按凭证载荷回查（arch/12 §8.1）。
    """
    png = await playback_service.render_book_page(
        session,
        media_id=media_id,
        page_no=page_no,
        token=token,
        ip=client_ip(request),
    )
    return Response(
        content=png, media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@router.get(
    "/media/{media_id}/subtitles.vtt",
    dependencies=[Depends(get_kb_authorized_user)],
)
async def get_subtitles(
    media_id: int,
    user: Annotated[User, Depends(get_kb_authorized_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """字幕轨：文稿分段生成 WebVTT（apiClient Bearer 鉴权，query token 留给 video src）。"""
    vtt = await playback_service.build_subtitle_vtt(session, media_id=media_id)
    return Response(
        content=vtt,
        media_type="text/vtt; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/images/{image_id}/original-url",
    response_model=KbImageUrlResponse,
    dependencies=[Depends(get_kb_authorized_user)],
)
async def get_image_original_url(
    image_id: int,
    user: Annotated[User, Depends(get_kb_authorized_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KbImageUrlResponse:
    """图片原图短时效预签名（≤15min；管理台 1h 口径不带入消费页）。"""
    return await playback_service.issue_image_url(session, image_id=image_id)
