"""视觉通道共享件：域异常、时间码格式化与管理面审计常量。"""

from datetime import timedelta


class VisionError(RuntimeError):
    """视觉管线本机环节失败（ffmpeg 缺失/失败、素材不可读）。"""


AUDIT_IMAGE_REDESCRIBE = "kb.image.redescribe"
AUDIT_IMAGE_EXCLUDE = "kb.image.exclude"

_THUMB_URL_TTL = timedelta(hours=1)


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "?"
    total_seconds = ms // 1000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
