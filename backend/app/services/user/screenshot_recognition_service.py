"""自选股截图识别服务：视觉模型识别 + stock_basic 交叉校验。

识别由 ``app/agent/skills/watchlist_screenshot_recognition`` 执行器完成
（函数内延迟导入以避免 services → agent 反向依赖）。
"""

import structlog
from pydantic import ValidationError
from pydantic_ai import BinaryContent
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market.stock_repository import StockRepository
from app.schemas.user import WatchlistScreenshotRecognitionItem

logger = structlog.get_logger()

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class ScreenshotValidationError(ValueError):
    """截图不满足识别要求（类型/大小）。"""


async def recognize_screenshot(
    session: AsyncSession, data: bytes, content_type: str | None
) -> list[WatchlistScreenshotRecognitionItem]:
    """识别截图中的股票并与 ``stock_basic`` 交叉校验。

    命中策略：代码优先（识别代码存在于 stock_basic 即 valid）；
    代码未命中但识别名称精确匹配时，以库内代码回填。

    Raises:
        ScreenshotValidationError: 图片类型或大小不符合要求。
    """
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ScreenshotValidationError(
            f"不支持的图片类型：{content_type or '未知'}，仅支持 png/jpeg/webp"
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise ScreenshotValidationError("图片超过 8MB 限制")

    from app.agent.skills.watchlist_screenshot_recognition import run_skill

    try:
        recognized = await run_skill(
            session, BinaryContent(data=data, media_type=content_type)
        )
    except ValidationError as exc:
        logger.warning("watchlist_screenshot_recognition_invalid_output", error=str(exc))
        return []

    if not recognized:
        return []

    stock_repo = StockRepository(session)
    codes = [item.code for item in recognized]
    names = [item.name for item in recognized if item.name]
    names_by_code = await stock_repo.get_names_by_codes(codes)
    codes_by_name = await stock_repo.get_codes_by_names(names)

    items: list[WatchlistScreenshotRecognitionItem] = []
    seen: set[str] = set()
    for row in recognized:
        code = row.code
        name = row.name
        matched = names_by_code.get(code)
        if matched is None and name is not None:
            fallback = codes_by_name.get(name)
            if fallback is not None:
                code = fallback
                matched = names_by_code.get(code) or name
        if code in seen:
            continue
        seen.add(code)
        items.append(
            WatchlistScreenshotRecognitionItem(
                stock_code=code,
                stock_name=name,
                confidence=row.confidence,
                valid=matched is not None,
                matched_name=matched,
            )
        )
    return items
