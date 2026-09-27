"""知识库任务声明（F-KB）：课程转写、知识点抽取、视频关键帧与 ES 索引构建（增量/蓝绿重建）。"""

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
        # 多窗口 LLM 结构化调用：整课回填实测 40 分钟+（68 集约 1 集/分钟），
        # 与转写同级长任务——走 heavy 专用 worker，避免占满主 worker 槽位饿死实时采集
        queue="heavy",
        soft_time_limit=3600,
        hard_time_limit=4200,
    ),
    TaskSpec(
        name="kb-vision",
        label="视频关键帧理解",
        description="扫描 done 视频三路信号选帧入 COS（vision_at 幂等），再对 pending 帧批量 VLM 描述",
        data_type="kb_vision",
        collectors={
            "internal": "collector.spiders.kb_vision:KbVisionCollector",
        },
        # 选帧逐集 ffmpeg 抽帧 + 描述阶段逐张 VLM 调用：大批量回填可达小时级，
        # 走 heavy 专用 worker；单轮超限被杀后按 vision_at/pending 帧增量续跑
        queue="heavy",
        soft_time_limit=3600,
        hard_time_limit=4200,
    ),
    TaskSpec(
        name="kb-index",
        label="知识库索引构建",
        description="三类脏行（知识点/分段/图片）增量向量化入 PG halfvec 列；force_rebuild=true 蓝绿全量重建（切模型后必跑）",
        data_type="kb_index",
        collectors={
            "internal": "collector.spiders.kb_index:KbIndexCollector",
        },
        run_params=("force_rebuild",),
        # 嵌入批量短调用 + 行内 UPDATE，正常增量为分钟级；全量重建受各类 500/轮限流
        queue="batch",
        soft_time_limit=1800,
        hard_time_limit=2100,
    ),
)
