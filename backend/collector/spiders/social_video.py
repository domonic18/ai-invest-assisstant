"""抖音大 V 视频采集器（PostgresCollector 薄壳）。

账号遍历、增量判新、ASR 转写在 ``collection_service`` 完成；本类只声明
存储契约（(platform, video_id) 冲突键幂等入库，冲突 DO NOTHING——已入库
内容与 ASR 记账永不回写）。通道级失败由 service 向上传播，BaseCollector.run
统一转 FAILED（F-MON 告警 + 资讯 Tab 横幅）。
"""

from typing import Any

from app.core.database import AsyncSessionLocal
from app.services.social import collection_service
from collector.core.base import PostgresCollector


class SocialVideoCollector(PostgresCollector):
    """抖音大 V 视频采集器。"""

    table = "social_post"
    conflict_key = "platform, video_id"
    normalize = False
    key_fields = ["platform", "video_id"]
    required_fields = ["platform", "video_id", "published_at"]

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """遍历启用账号采集新视频行（行不入库，由 store 幂等写入）。"""
        account_id = kwargs.get("account_id")
        backfill = bool(kwargs.get("backfill", False))
        async with AsyncSessionLocal() as session:
            return await collection_service.collect_all_accounts(
                session, account_id=account_id, backfill=backfill
            )
