"""知识库任务声明（F-KB）：课程转写（扫描 queued）、知识点抽取（扫描 done）与视频关键帧（两阶段）。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="kb-transcribe",
        label="知识库课程转写",
        description="扫描 queued 素材执行 ASR 转写（分片并发 + COS 缓存续跑），完成后入分段",
        data_type="kb_transcribe",
        collectors={
            "internal": "collector.spiders.kb_transcribe:KbTranscribeCollector",
        },
        # 单集长音频（抽音轨→分片→逐片 ASR→清洗）远超 BATCH 默认 300s
        queue="heavy",
        soft_time_limit=3600,
        hard_time_limit=4200,
    ),
    TaskSpec(
        name="kb-extract",
        label="知识点抽取",
        description="扫描转写完成素材做章节推断与滑窗知识点抽取（三层幻觉防线，草稿落库）",
        data_type="kb_extract",
        collectors={
            "internal": "collector.spiders.kb_extract:KbExtractCollector",
        },
        # 多窗口 LLM 结构化调用，长课程可能整轮超 BATCH 默认时限
        queue="batch",
        soft_time_limit=1800,
        hard_time_limit=2100,
    ),
    TaskSpec(
        name="kb-vision",
        label="视频关键帧理解",
        description="扫描 done 视频三路信号选帧入 COS（vision_at 幂等），再对 pending 帧批量 VLM 描述",
        data_type="kb_vision",
        collectors={
            "internal": "collector.spiders.kb_vision:KbVisionCollector",
        },
        # 选帧逐集 ffmpeg 抽帧 + 描述阶段逐张 VLM 调用，长视频可能超 BATCH 默认时限
        queue="batch",
        soft_time_limit=1800,
        hard_time_limit=2100,
    ),
)
