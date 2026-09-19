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

#: 分片上传会话最大保留天数（超龄由 kb-cleanup abort 释放已传分片）
KB_UPLOAD_SESSION_MAX_AGE_DAYS = 7

#: kb-cleanup 互斥锁与 deep 孤儿扫描的每日门控键
KB_CLEANUP_LOCK_KEY = "kb:cleanup"
KB_CLEANUP_DEEP_LOCK_KEY = "kb:cleanup:deep"

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

#: kb-extract 任务级互斥锁键
KB_EXTRACT_LOCK_KEY = "kb:extract"

#: 单素材连续抽取失败上限（process_meta.extractAttempts 达到后不再扫，需人工排查）
KB_EXTRACT_MAX_ATTEMPTS = 3
