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
    """三类检索行（检索接口 kind 过滤值）。"""

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

#: 检索列向量维度（halfvec 列类型钉死；换维度 = 列迁移 + 索引重建 + 全量重嵌）
KB_EMBEDDING_DIMS = 2048

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

#: kb-vision 任务级互斥锁键
KB_VISION_LOCK_KEY = "kb:vision"

#: 关键帧选帧场景切换检测阈值（ffmpeg select='gt(scene,T)'）
KB_VISION_SCENE_THRESHOLD = 0.3

#: 定长兜底采样间隔（秒，画面渐变型课程的保底采样路）
KB_VISION_FIXED_INTERVAL_SECONDS = 60

#: 多信号时间窗合并阈值（秒，窗口内命中保留 1）
KB_VISION_MERGE_WINDOW_SECONDS = 5

#: aHash 汉明距离去重阈值（≤ 视为近重复丢弃）
KB_VISION_PHASH_HAMMING_THRESHOLD = 5

#: 单集关键帧硬上限（超限按信号优先级裁剪）
KB_VISION_MAX_FRAMES_PER_MEDIA = 120

#: 单帧视觉描述连续失败上限（describe_attempts 达到后终态 failed）
KB_VISION_MAX_DESCRIBE_ATTEMPTS = 3

#: 单集选帧连续失败上限（process_meta.visionAttempts 达到后不再扫）
KB_VISION_MAX_MEDIA_ATTEMPTS = 3

#: 单轮描述阶段的 VLM 调用上限（控制任务时长与费用节奏，余量下轮续跑）
KB_VISION_DESCRIBE_BATCH_SIZE = 20

#: 关键帧抽帧半窗（秒，取 t±2s 中较清晰的一帧）
KB_VISION_SEEK_TOLERANCE_SECONDS = 2

#: kb-index 任务级互斥锁键
KB_INDEX_LOCK_KEY = "kb:lock:index"

#: kb-index 单轮各类行的批量上限（控制单轮时长与嵌入请求节奏，余量下轮续跑）
KB_INDEX_BATCH_SIZE = 500

#: 视觉指涉句正则（文稿引导采样路：命中句取句中点时刻）
KB_VISION_GUIDE_PATTERNS = (
    "你看",
    "如图",
    "这条线",
    "这个下降通道",
    "这个上升通道",
    "这个中枢",
    "这个背离",
    "这个金叉",
    "这个死叉",
    "这个买点",
    "这个卖点",
    "这个缺口",
    "这个均线",
    "这个形态",
    "这个指标",
    "这个走势",
    "这个图形",
)
