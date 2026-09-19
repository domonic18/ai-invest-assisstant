"""知识库任务声明（F-KB）：课程转写（状态驱动，扫描 queued 素材）。"""

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
)
