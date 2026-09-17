"""抖音自研适配层（F-SOC）：TLS 指纹传输、a_bogus 签名、Cookie 双轨、Web API 封装。"""

from app.adapters.douyin.api import (
    DouyinPostsPage,
    DouyinProfile,
    DouyinVideo,
    DouyinWebApi,
)
from app.adapters.douyin.transport import DouyinTransport

__all__ = [
    "DouyinPostsPage",
    "DouyinProfile",
    "DouyinTransport",
    "DouyinVideo",
    "DouyinWebApi",
]
