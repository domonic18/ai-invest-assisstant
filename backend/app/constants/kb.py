"""知识库域共享常量（F-KB：模型校验、任务扫描与凭证键的单一来源）。"""

from enum import Enum


class KbSourceType(str, Enum):
    """知识源类型。"""

    COURSE = "course"
    BOOK = "book"


class KbMediaKind(str, Enum):
    """素材类型（书的 episode_no 恒为 NULL）。"""

    VIDEO = "video"
    AUDIO = "audio"
    BOOK = "book"


class KbProcessStatus(str, Enum):
    """素材建库状态机：uploaded → awaiting_cost → queued → processing → done / failed。"""

    UPLOADED = "uploaded"
    AWAITING_COST = "awaiting_cost"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class KbPointType(str, Enum):
    """知识点类型。"""

    CONCEPT = "concept"
    THEOREM = "theorem"
    METHOD = "method"
    DISCIPLINE = "discipline"
    CASE = "case"


class KbPointStatus(str, Enum):
    """知识点审核状态：仅 published 参与索引与检索。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    REJECTED = "rejected"


class KbDescribeStatus(str, Enum):
    """图片视觉描述任务状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class KbDocKind(str, Enum):
    """ES kb-knowledge 索引的三类文档。"""

    POINT = "point"
    SEGMENT = "segment"
    IMAGE = "image"


class KbPurpose(str, Enum):
    """llm_config 用途维度（管线模型角色绑定校验）。"""

    CHAT = "chat"
    EMBEDDING = "embedding"
    VISION = "vision"


#: 软删恢复窗口（过窗后 kb-cleanup 异步清理）
KB_SOFT_DELETE_RECOVERY_HOURS = 24

#: 播放凭证 TTL 上限（秒，需求 ≤30min）
KB_PLAYBACK_TOKEN_TTL_SECONDS = 1800

#: 播放凭证 Redis 键模板（值为 {userId, mediaId} JSON）
KB_PLAYBACK_TOKEN_KEY_TEMPLATE = "kb:playback:{token}"

#: 知识库转写并发锁键（防多 worker 同时消化同一素材）
KB_TRANSCRIBE_LOCK_KEY_TEMPLATE = "kb:lock:transcribe:{media_id}"

#: 知识点抽取滑动窗口时长（秒）
KB_EXTRACT_WINDOW_SECONDS = 600

#: 窗口间重叠上下文分段数
KB_EXTRACT_WINDOW_OVERLAP_SEGMENTS = 1
