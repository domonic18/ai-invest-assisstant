# 知识库架构设计（温成趋势理论 · F-KB）

> 闭环：后台登记多知识库（课程/电子书）→ 文件夹批量直传 COS → 课程 ASR 分片转写（句级时间戳）+ 视频关键帧抽取（三路信号选帧 + VLM 描述）/ 电子书文本层解析（PyMuPDF + 嵌入图片资产）→ LLM 章节推断 + 知识点抽取 → 人工审核发布 → **PG 同库混合检索（`halfvec` 向量 + `pg_trgm` 词面，服务层 RRF）**→ 内部检索页（片段播放器/阅读器，代理 + 短时效凭证防盗）→ Agent 运行时引用（会话级知识库开关门控）。
> 需求：[docs/requirement/04-knowledge-base-requirement.md](../requirement/04-knowledge-base-requirement.md)（F-KB V1.1）· 原型：[docs/prototypes/knowledge-base.html](../prototypes/knowledge-base.html)
> 调研基线（2026-09）：pgvector 0.8.1 + pg_trgm 1.6（TimescaleDB 镜像内可用；2048 维必须用 `halfvec`——`vector` 类型 HNSW 上限 2000 维；en_US.utf8 ctype 下 CJK 三元组正常生成）；MiniMax ASR 仅 `asr-1.0`（≤500s/50MB/次，无热词参数，句级时间戳可用，单价未公开刊例）；MiniMax M3 为多模态对话模型、非识别模型，定位在转写后清洗与知识抽取。**电子书确认为文字版 PDF**（2026-09-18 拍板）：单通道文本层解析，扫描版 OCR 后置（出现扫描版素材再立项）。

## 1. 设计原则

1. **PG 是唯一存储，检索面同库内嵌（无投影层）**：知识点/分段/图片资产的文本、状态、定位与检索列（`search_text` 生成列 + `embedding halfvec`）同表存放；文稿编辑、知识点修订通过 `embedding_dirty` 脏标记传播，物化任务增量覆写 `embedding`。不存在第二存储，也就不存在投影漂移/丢文档/孤儿文档这类双存储一致性问题（2026-09-20 拍板：检索去投影化，收敛原 ES 投影实现）。
2. **语义流与定位流解耦**：embedding 输入是清洗后的纯文本，时间戳/页码/集号只走元数据字段不进向量——检索质量与定位精度（±2s 目标）互不牵制，这是音频 RAG 的定式。
3. **三类检索行、一套查询语义**：知识卡片（point）/ 内容分段（segment）/ 图片资产（image）三表各自内嵌检索列，检索服务按 `kind` 语义分桶融合。卡片命中给「概念级答案」，分段命中给「原文取证」，图片命中给「文字搜图」；命中行即真相行，水合只补媒体定位与签名。语料量级 ≤1 万行，同库双索引余量充足。
4. **建库任务是状态驱动的 internal worker，费用确认是状态门**：HTTP 端点只改状态与预估，四类任务（转写/解析/抽取/索引）扫描 `pending`/`dirty` 行增量推进（最终一致，非实时）；素材 `awaiting_cost` 状态不经管理员确认不会变 `queued`——成本闸门内建于状态机，不依赖端点自觉。
5. **复用不重建，零新增部署容器**：collector internal 任务体系、`run_structured`（全字段 required 铁律）、`asr_channel_config`（F-SOC 已建，渠道凭据复用）、MinIO 封装（私有桶 + 预签名）、`UsageMeterCallback` 系统维度计量、CamelModel wire、redis_lock、F-MON——全部沿用；电子书文字版单通道后（2026-09-18 拍板）不引入任何解析 sidecar，主镜像只添轻量 Python 依赖（pymupdf / pypdfium2 / Pillow）。
6. **检索底座为 PG 单库**（2026-09-20 拍板，取代早期 ES 投影方案）：词面路走 `pg_trgm`（ILIKE 子串候选 + `similarity()` 排序，GIN 加速），向量路走 `halfvec(2048)` HNSW（`halfvec_cosine_ops`，`<=>` 余弦距离），融合在服务层 RRF（<30 行，k=60）。判定依据：语料 ≤1 万行量级 PG 双索引余量充足；双存储投影的同步链是独立故障面（best-effort 删除、投影被外部清空、版本对账皆由此生）；中文词法在 PG 外需额外分词扩展与容器，而 trgm 子串召回 + 向量语义路对当前查询形态（术语与长短自然语言混合）已覆盖。语料涨至数十万级或需要词频权重排序时再评估专门检索引擎。
7. **防盗是纵深组合**：私有桶直链永不透出 + 后端鉴权代理（视频 Range 透传 / 书页按需位图渲染）+ 一次性短时效凭证（≤30min，绑定用户与素材）+ 异常拉取审计 + 水印（书页服务端烧录、播放画面前端角标）——技术目标是显著抬高批量盗取成本，不承诺防录屏（需求边界）。
8. **模型角色全部后台配置，用量统一台账**：管线四类模型角色——清洗（chat）/ 知识抽取（chat）/ 图片理解（vision）/ 向量嵌入（embedding）——全部落 `llm_config` 配置条目，`kb_settings` 持角色槽位引用，admin 可随成本与质量切换，代码不硬编码模型名；全部 LLM/embedding 调用计入既有 `user_token_usage` 台账（`kb_*` feature + 上下文 detail），ASR 时长型用量入 `kb_media.process_meta`——建库成本随时可评估（§14）。

## 2. 数据模型

迁移 `docker/database/migrations/20260918_knowledge_base.sql`（幂等）+ `init-scripts/01-schema.sql` 双写（[03-data-storage](./03-data-storage.md) 规范）；SQLAlchemy 模型落 `backend/app/models/kb.py`（单数表名 + `kb_` 前缀，`Mapped` 2.0 风格，审计字段走 `app.core.clock.utc_now`）。

| 表 | 键与约束 | 说明 |
|----|----------|------|
| `kb_source` | `source_type CHECK ('course','book')`；`deleted_at`（软删） | `name`/`author`（讲师·作者，按类型展示标签）/`description`/`enabled`；`chapter_tree JSONB`（`{draft, published}` 两棵树，节点 `{id, title, children}`，节点 id 稳定）；`storage_bytes BIGINT`（COS 登记字节数聚合）、`pending_cleanup_bytes`（异步清理未完成量） |
| `kb_media` | uq `(source_id, episode_no)` WHERE episode_no IS NOT NULL；uq `(source_id, file_hash)`（去重）；idx `(source_id, process_status)` | `media_kind CHECK ('video','audio','book')`；`episode_no INT NULL`（课程集号）、`title`、`file_name`、`cos_key`、`file_size`、`file_hash`；`duration_seconds`/`page_count`（按类型）；`process_status CHECK ('uploaded','awaiting_cost','queued','processing','done','failed')` + `process_error`；`process_meta JSONB`（用量对账：provider/model/audio_seconds/chunk_count/est_cost…）；`edited_at TIMESTAMPTZ NULL`（文稿人工编辑时刻，脏传播源）；`vision_at TIMESTAMPTZ NULL`（课程视频关键帧选帧完成时刻，视觉通道幂等键） |
| `kb_transcript_segment` | uq `(media_id, seq_no)`；idx `(source_id, embedding_dirty)`、GIN `(text gin_trgm_ops)` | 泛化内容分段：课程 `start_ms`/`end_ms`（句级时间码），电子书 `page_start`/`page_end`（跨页段落合并后为页区间）；`text`（词面检索列兼嵌入输入）；`embedding halfvec(2048) NULL`；`embedding_dirty BOOLEAN DEFAULT true`（新建/编辑即脏，物化任务增量拾取） |
| `kb_knowledge_point` | idx `(source_id, status)`、`(embedding_dirty)`、GIN `(chapter_path jsonb_path_ops)`、HNSW/GIN 检索索引（见下） | `point_type CHECK ('concept','theorem','method','discipline','case')`；`title`/`body`（正文，保留讲师表述）/`term_definition NULL`/`applicable_scene NULL`/`excerpt`（原文摘录）；`search_text` 生成列（title/term_definition/body/applicable_scene 拼接，词面检索列兼嵌入输入）+ `embedding halfvec(2048) NULL`；定位：`media_id FK` + `start_ms`/`end_ms`（课程）或 `page_start`/`page_end`（书）；`related_ids JSONB`；`chapter_path`（发布树节点 id 串）；`status CHECK ('draft','published','rejected')`；`needs_review BOOLEAN`（excerpt 校验未过的显式标记）；`review_note`/`reviewed_by`/`reviewed_at` |
| `kb_image_asset` | idx `(source_id, embedding_dirty)`、HNSW/GIN 检索索引（见下） | 图片资产（书嵌图 + 课程视频关键帧统一落表，逐张生命周期需要独立行）：`media_id FK CASCADE`、`page_no INT NULL`（书页码）、`start_ms`/`end_ms BIGINT NULL`（课程关键帧时间码）、`bbox JSONB NULL`、`cos_key`（原图）、`thumb_cos_key`（缩略图）、`text_in_image`/`caption`/`vision_description`、`search_text` 生成列（三文本拼接，词面检索列兼嵌入输入）+ `embedding halfvec(2048) NULL`、`describe_status CHECK ('pending','processing','done','failed')` + `describe_attempts INT DEFAULT 0`（失败退避，≥3 终态 failed） |
| `kb_settings` | 单行 | `hotwords JSONB`（金融热词表，注入清洗 prompt）、`segment_max_seconds INT DEFAULT 30`、`asr_concurrency INT DEFAULT 2`、`top_k INT DEFAULT 8`、`auto_approve_points BOOLEAN DEFAULT true`（三层防线全过的抽取点自动 published，任何校验触碰仍走人工队列）、`unit_prices JSONB`（`{asrPerHour, vlmPerImage}` 参考单价，费用预估用）、`authorized_user_ids JSONB`（知识库授权白名单；admin 隐含授权）；**模型角色槽位**（均 FK `llm_config.id`，admin 后台可切换）：`embedding_config_id`（用途=embedding）、`clean_model_id`（转写清洗，chat）、`extract_model_id`（章节推断+知识抽取，chat）、`vision_model_id`（图片理解，vision） |

连带两处既有表扩展：

- `llm_config` 增列 `purpose VARCHAR(16) DEFAULT 'chat' CHECK IN ('chat','embedding','vision')`（既有行不动，默认 chat）。管线代码不硬编码模型名，一律经 `kb_settings` 角色槽位解析到 `llm_config` 条目：LLM 三角色（清洗/抽取/视觉）走 `run_structured(..., config_id=<槽位指向的条目>)`（`run_structured` 增可选 `config_id` 参数，缺省回落现有 `resolve_llm`）；embedding 走该条目的 OpenAI 兼容 `/v1/embeddings`（bge-m3 1024 维，cosine），小客户端 `embedding_client.py` 直连，不经 langchain。后台启动/保存校验：四槽位必须已配置且条目 `purpose` 与角色匹配。
- `user_token_usage`（F-ACCT 已建）增列 `detail JSONB NULL`——建库用量复用这张台账而非新建表：`user_id NULL` = 系统维度（建库管线均为 system），`feature` 取 `kb_clean` / `kb_extract` / `kb_vision` / `kb_embed`，`detail` 存 `{sourceId, mediaId, taskRunId}` 上下文供按知识库聚合。embedding 客户端不经 langchain、无 UsageMeterCallback 回调，自行经 `usage_writer.enqueue` 记账；清洗/抽取/视觉走 `run_structured`，由 `UsageMeterCallback` 自动入账。ASR 时长型用量（非 token）继续落 `kb_media.process_meta`。

**检索列与索引**（同库，扩展 `vector` + `pg_trgm`）：三表 `embedding halfvec(2048) NULL`（`vector` 类型 HNSW 上限 2000 维，2048 维必须 `halfvec`，fp16 存储对余弦排序影响可忽略）；point/image 的 `search_text` 为生成列（拼接口径 = 嵌入输入口径，单一真相），segment 词面列直接用 `text`。检索索引：三表 `HNSW(embedding halfvec_cosine_ops)`、point/image `GIN(search_text gin_trgm_ops)`、segment `GIN(text gin_trgm_ops)`。模型换维度属罕见操作 = 一次性列类型迁移 + 索引重建 + 全量重嵌（§7.3）。ES 已全栈退役（2026-09-21，研报/财报全文入 `file_metadata.content` + pg_trgm），KB 链路零 ES 连接。

## 3. 素材接入与存储（F-KB-01）

```
文件夹拖拽（前端 webkitdirectory / DataTransferItem 保持目录结构）
  → POST /admin/kb/sources/{id}/media/init   # 批量建 draft 行 + 单 PUT 预签名（大文件直传 COS）
  → 前端逐文件直传（进度入上传队列；Web Worker 预算整文件 MD5 供去重）：
       ≤64MB 单 PUT；>64MB multipart 分片直传（16MB/片、3 片并发、逐片 MD5 对 ETag 核对、刷新页面断点续传）
         ├─ POST   .../media/{mid}/upload-session   # 建/续会话：uploadId + 仅缺失分片的签名 URL（服务端 list_parts 为续传真相）
         └─ DELETE .../media/{mid}/upload-session   # 放弃会话（幂等，abort 释放已传分片）
     → POST .../media/{mid}/uploaded
          └─ 服务端核对：单 PUT HEAD size/etag；分片 list_parts 汇总 = declaredSize → complete → HEAD size 复核
             → 去重校验（同库同哈希 409，部分唯一索引仅约束存活行）→ 状态 uploaded
  → 管理员「预估建库费用」→ POST cost-estimate（时长/页数/图片数 × unit_prices）→ 确认 → awaiting_cost → queued
```

- 集号：按目录文件名自动编号，PATCH 可调（uq 约束兜底）；电子书按书册登记（同名书多版本 = 同 source 多 media 行）。
- 外部文稿导入（TXT/SRT）：init 时带 `transcriptOverride`，跳过 ASR 直接入分段（状态直通 done）。
- **分片会话**：`process_meta` JSONB 存 `{uploadId, partSize, partCount, sessionStartedAt, declaredSize}`，无独立表；超龄（7 天）会话由 `kb-cleanup` abort 释放已传分片。
- **存储大小**：上传/删除即时增减 `kb_source.storage_bytes`（登记字节数聚合）；异步清理未完成期间叠加 `pending_cleanup_bytes` 展示。
- **级联删除**：DELETE 为软删（`deleted_at`，列表即隐藏，24h 内可恢复）→ `kb-cleanup` internal 任务（`*/30` 扫描）清除过窗软删行（素材/知识源级联，含旗下素材）：COS 批量删对象 → 硬删行 → `pending_cleanup_bytes` 清零；deep 孤儿扫描每日一次（Redis 门控）：`kb/` 前缀有对象而无存活行引用（含软删未过窗）即删。删除知识库/素材/单集均走同一路径；行硬删即检索面同步消失（同库同事务，无投影清理）。

## 4. 课程转写（F-KB-02）

任务 `kb-transcribe`（internal，heavy 队列）扫 `process_status='queued'` 的 video/audio 素材，单轮受 `asr_concurrency` 约束：

```
ffmpeg 抽 16kHz 单声道 wav
  → 静音切分（ffmpeg silencedetect，-30dB / 最短静音 0.5s；无静音兜底定长切）→ 分片 ≤480s（asr-1.0 硬限 500s 内留余量）
  → 逐片调 asr-1.0（verbose_json，timestamp_level=sentence）            # 并发=asr_concurrency
  → 分片结果缓存 COS derived 前缀（kb/derived/{media_id}/chunks/）        # 断点续跑：重跑跳过已存在分片，不重复计费
  → 全局偏移合并 → 标点 + ≤segment_max_seconds 切句 → 全局句级时间戳
  → 清洗（chat 模型单轮：热词表入 prompt，只改错字/术语/去语气词，逐句对应不改时间戳）   # MiniMax 无热词参数的既定弥补方案，成本分钱级
  → kb_transcript_segment 落库（逐片 commit）→ process_status=done + process_meta{provider, model, audio_seconds, chunk_count, est_cost}
```

- 状态机 `queued → processing → done / failed`，进度按「已转写时长/总时长」透出；渠道不可用/超限（400/413）显式 FAILED 归因写 `process_error`，不静默重试烧钱。
- 清洗模型经 `kb_settings.clean_model_id` 角色槽位解析（`run_structured(config_id=...)`，M2.5/M3 同价位均可，1 集约 1 万 tokens）；调用经 `UsageMeterCallback` 自动计量入台账（feature=kb_clean，system 维度）。
- **文稿可人工编辑**（质量最后防线）：后台编辑器批量保存 → 更新 `kb_media.edited_at` + 命中分段置 `embedding_dirty`（索引增量同步，知识点正文不受影响——人工审定产物）。
- ASR 凭据复用 `asr_channel_config`（F-SOC 已建，Fernet 加密 + masked 展示 + test_connection）；知识库域参数（并发/热词/单价/分段上限）在 `kb_settings`，渠道与域参数分离。若 asr-1.0 实测单价显著高于阿里 Paraformer（≈¥0.29/小时），渠道层可配置切换（`asr_channel_config.provider` 预留），管线不变。

### 4.1 课程视频关键帧通道

转写只消费音频，视频画面的盘面讲解（画线/指标/走势）不进知识库。轻量关键帧通道补齐该维度，原则与电子书图片资产同构：**帧图本身是检索产物**（文字搜图 → 缩略图 + 时间码 → 跳播），不是给 LLM 看视频。

**三路信号选帧**（互补盲区）：

1. **场景切换检测**（主讲切 PPT/切屏）：`ffmpeg select='gt(scene,0.3)' + showinfo`，从 stderr 解析 `pts_time`；
2. **定长兜底**（~60s 间隔）：画面渐变型课程（无切换）的保底采样；
3. **文稿引导采样**（关键路）：对既有 `kb_transcript_segment` 文本做视觉指涉句正则（「你看 / 如图 / 这条线 / 这个下降通道 / 这个中枢」…），取句中点时刻——盘面讲解类课程的关键帧往往无场景突变，只有此路能命中「画线瞬间」。

**去重与配额**：多信号时间窗合并（<5s 命中保留 1，优先级 ③>①>②）→ aHash 感知哈希（ffmpeg 16×16 灰度 rawvideo 输出，纯 Python 汉明距离，不引 Pillow）滤近重复 → 单集硬上限 ~120 张，超限按信号优先级裁剪。

**两段式成本分层**：

- **选帧阶段零 LLM**：ffmpeg 按时刻抽帧 → aHash 去重 → 原图/缩略图传 COS（`kb/derived/{media_id}/frames/{start_ms:012d}.jpg`）→ `kb_image_asset` 行（`describe_status='pending'`，`start_ms` 定位）→ `kb_media.vision_at=now()`（幂等键，重跑不重抽）；
- **描述阶段按张计费**：扫 `describe_status='pending'` 行，`run_structured(ImageUnderstanding, images=[帧], vision=True, config_id=kb_settings.vision_model_id)`（复用 §5.1 Schema，三文本全 required），prompt 附该时间码前后句文稿作上下文（§5.1 前后页文本同款技巧）；失败 `describe_attempts+1` 退避，≥3 终态 failed。

任务接线见 §13 `kb-vision`；费用入台账（feature=kb_vision，detail 带 mediaId）。

**边界**：MiniMax M3 原生视频输入（≤30min）记为二期增强备选——整视频喂入 token 成本 ~1fps 等效、远高于按张计费，且帧图已是检索交付物；二期若做片段级时序理解（15–30s 关键操作片段动态描述），经既有 vision 槽位扩展视频 content block 即可，不新增表。

## 5. 电子书解析与图片资产（F-KB-10）

素材准入即约束：**仅收文字版 PDF**（上传说明 + 解析时校验）。任务 `kb-book-parse`（batch 队列）扫 queued 的 book 素材，单通道无分支：

```
PyMuPDF 逐页文本层抽取（有效字符数过低页显式计入 process_meta.warn_pages，交人工判断是否扫描版误传）
  → 段落归并（跨页段落合并，页码区间作元数据）→ 分段（page_start~page_end）
  → get_images 抽取嵌入图片（bbox + 页码）→ kb_image_asset 行（原图/缩略图传 COS）
  → VLM 描述（§5.1）→ done
```

- **无 OCR 通道**：出现扫描版素材（文本层缺失）= 解析 FAILED 显式归因「疑似扫描版，不收」，不静默产出低质分段；扫描版 OCR 后置，出现真实扫描素材再立项。
- 抽取质量护栏：逐页字符数与图片占比写 `process_meta`（`{provider: 'pymupdf', pageCount, warnPages, imageCount}`），预估失真有据可查。
- 验收口径：正文可检索、页码定位准确，不承诺排版还原。

### 5.1 图片资产 → 文字搜图

- 每图一次 VLM 调用：`run_structured(ImageUnderstanding, images=[图], vision=True, config_id=kb_settings.vision_model_id)`，Schema `{text_in_image, caption, description}` **全字段 required**（图内文字 OCR + 图注推断 + 视觉描述一体）；prompt 附前后页文本作上下文。
- VLM 模型后台可配（`vision_model_id` 槽位指向 `llm_config` vision 条目，qwen-vl / GLM-4V / MiniMax VL-01 均可接入）；约 300 页书 ≤500 图，成本 <¥10 量级。
- 三文本（图内文字/图注/描述）合并入 image 行 `search_text` 生成列 → query 命中返回缩略图（代理签名）+ 页码定位。

## 6. 章节推断与知识抽取审核（F-KB-03）

任务 `kb-extract`（internal）扫「转写/解析 done 且未抽取」的素材，服务层编排两步：

- **章节推断**（每知识源一次）：逐集大纲 `run_structured(EpisodeOutline, config_id=kb_settings.extract_model_id)` → 跨集合并单次调用生成目录树草稿 → 写 `kb_source.chapter_tree.draft`；审核工作台逐节点确认/修订/拖拽 → 发布为 `published`（节点 id 稳定，知识点 `chapter_path` 引用）。
- **知识点抽取**（按素材滑动窗口 ~10 分钟，窗口间带 1 段重叠上下文）：`run_structured(KbExtractionResult, config_id=kb_settings.extract_model_id)`，Schema `{points: [{title, body, point_type, term_definition, applicable_scene, excerpt, start_ms, end_ms, related_titles}]}`——**全字段 required、禁带默认值**（项目铁律，钉死单测）。幻觉防线三层：
  1. **定位校验**：时间码越界 clamp/丢弃（对齐 K 线画线锚点校验先例）；
  2. **摘录校验**：`excerpt` 须在素材分段中模糊命中（归一化后包含性判断），未过 → `needs_review=true` 交人工，不自动驳回；
  3. **关联校验**：`related_titles` 按标题回链同库知识点，未匹配剔除（sentiment 幻觉标的过滤同款）。
- **审核工作台**：draft → `published` / `rejected` / 修订后通过（仅 title/type/body/term/scene/chapter_path 可改，**原文摘录与定位不可改**）；支持人工新增、合并重复、维护关联。**自动通过门**（`kb_settings.auto_approve_points`，默认开）：三层防线全过（定位零越界、摘录精确命中、关联零剔除）的抽取点直接 `published`，任何校验触碰（needs_review/clamp/剔除）仍落人工队列。仅 `published` 可检索（publish 置 `embedding_dirty` 待物化；驳回/删除改行状态即检索失效，同库无投影同步）。
- 抽取调用 Celery 路径 system 维度，费用经 UsageMeter 自动计量入台账（feature=kb_extract）；技能资产 `skills/kb-extract/{SKILL.md, prompt.yaml}`。

## 7. 嵌入物化与混合检索（F-KB-04）

### 7.1 嵌入物化（任务 `kb-index`，5 分钟心跳）

扫三类脏行批量推进（单轮上限 + embedding 批量 64/请求）：`point(status=published, dirty)` → `embedding = embed(search_text)`；`segment(dirty)` → `embedding = embed(text)`；`image(describe done, dirty)` → `embedding = embed(search_text)`；写入与清脏同事务。`kb_source.enabled=false` 或素材未 done 的不物化。embedding 客户端不经 langchain，批量调用后按响应 `usage` 自行 `usage_writer.enqueue` 记账（feature=kb_embed，detail 带 source_id/media_id）。全量重嵌（admin 触发或模型切换）：`force_rebuild` 全量置脏后一轮消化；行级覆写，重嵌期间旧向量仍可查——无别名/版本/对账机制。

### 7.2 检索服务（P95 < 500ms 预算主要花在 query embedding）

```
query ─→ embedding（与槽位模型同维度）─┬─ 词面路：search_text/text ILIKE '%q%' 候选（GIN trgm 加速）
   （query 向量 LRU 缓存可选）          │   → similarity() 排序，窗口 50
                                       └─ 向量路：ORDER BY embedding <=> qvec（HNSW），k=20×
        └─ 服务层 RRF 融合（k=60，仅看排名不需分数归一化）─→ kind 分组
             ├─ point：top_k（默认 8，卡片加权）→ 行即真相（水合只补媒体定位/缩略图签名）
             ├─ segment：原文取证按与命中卡片定位重叠就近挂载 + 独立命中列表
             └─ image：缩略图（短时效签名）+ 页码
   过滤器全链路透传：source_id / chapter_path 前缀（jsonb @>）/ point_type / kind
   （行内 WHERE 与水合口径同源——单一存储天然一致，无投影滞后窗口）
```

- 两路独立降级：embedding API 失败 → 仅词面路（响应 `degraded=embedding_unavailable`）；检索面与库同生命周期，无独立检索面停机语义。
- 课程命中附**前滚上下文**：播放起点 = `max(0, start_ms − 4000)`（需求 3~5s 口径）。

### 7.3 embedding 模型切换

`kb_settings.embedding_config_id` 变更 → admin 触发全量重嵌：同维度直接覆写 `embedding` 列（行级替换，检索不中断）；换维度 = 先执行列类型迁移（`ALTER ... TYPE halfvec(n)` + HNSW 索引重建）再全量重嵌——维度由列类型钉死，物化任务前置校验实测维度与列定义不符时 SKIPPED 显式报错引导。重嵌 token 消耗自然入台账（kb_embed），重建成本可事后核算。

## 8. 检索页、播放器与防盗（F-KB-05 + F-KB-09）

### 8.1 播放凭证与代理（安全面唯一入口）

```
POST /kb/media/{id}/playback-token   # 权限校验（admin / 白名单）→ Redis kb:playback:{token}={userId, mediaId} EX ≤1800
GET  /kb/stream/{mediaId}?token=     # 校验 token + 必须 Range 头 → MinIO get_object(offset/length) 206 透传（Content-Range/Accept-Ranges）
GET  /kb/books/{mediaId}/pages/{n}?token=  # pypdfium2 144DPI 按需渲染（干净页进程内 LRU）→ Pillow 叠用户水印 → PNG
GET  /kb/media/{id}/subtitles.vtt    # apiClient Bearer 鉴权（fetch 可带 header；query token 仅用于 <video> src）
GET  /kb/images/{id}/original-url    # 图片原图短时效预签名（≤15min，KB_IMAGE_ORIGINAL_URL_TTL_SECONDS）
```

- **异常拉取拦截**：无 token / token 过期 / 不绑定 → 401 + 审计事件 `kb.security.denied`；视频流无 Range 头（整文件抓取特征）→ 400 + 审计；连续异常触发账号级告警（管理端可见，封禁为管理员决策）。
- **前端不接触持久 COS 直链**：视频流与书页位图走代理（token + Range / 服务端水印烧录——干净页缓存与水印合成解耦，每请求一次轻量 composite）；缩略图与原图仅发短时效预签名（≤15min）。播放画面叠加静态角标（用户名 + 日期，前端层，安全不依赖此层）。
- 播放器禁下载交互（`controlsList=nodownload`、禁右键）为提高门槛的前端手段。

### 8.2 页面与播放器能力（对照原型 knowledge-base.html）

- 消费页 `/kb`（`web/src/pages/KnowledgeSearch/`，权限 = admin ∪ 白名单；侧边栏入口全员可见，未授权用户页面内 403 自解释引导）：搜索框 + 章节树导航 + 三类命中（卡片高亮 / 原文摘录 / 图片缩略图+页码）；命中展开显示集数 + `hh:mm:ss–hh:mm:ss` 或页码区间；管理台「知识检索」Tab 复用同一 SearchTab（双入口）。
- **KnowledgePlayer**：`<video src=/kb/stream/...?token>` + 自定义控制条——播放/暂停、进度条命中区间高亮（A/B 标记 + 循环）、倍速 0.5–2×（localStorage 记忆）、音量、全屏/画中画、键盘（Space/←→/↑↓）、断点续播（按 media 记忆）、上一集/下一集；**字幕联动**：WebVTT track + 当前端高亮 + 点击字幕句 seek（文稿即导航）；点击命中 → 自动 `seek(startMs − 前滚)`。
- **BookReader**：按页位图 + 页码跳转/前后页 + 命中页高亮标注 + 缩放；图片命中打开原图视图附页码上下文。
- 防盗边界声明（需求口径）：目标是抬高直接获取与批量盗取成本，录屏/翻拍以水印溯源震慑，不承诺根除。

## 9. Agent 消费（F-KB-06）

- **`search_knowledge_base(query, source?, chapter?, point_type?, include_media?)`** 工具：注册进 `build_assistant_tools()`，**按会话级知识库开关注入**（前端开关随 run metadata 下发 `use_kb`，纳入 agent 缓存指纹；关闭即不注册工具）。返回压缩卡片集（标题 + 正文 + 类型 + citation 定位：集数/时间码/章节/页码），token 预算受 top_k 约束；检索服务复用 §7.2（工具层薄封装）。`include_media=true` 仅在学习场景返回媒体定位（起播点/页码，前端渲染播放 chip）。降级：向量服务不可用返回明确 note，Agent 声明仅词面匹配。
- 分析类技能（大盘复盘/涨停复盘/异动归因/个股分析/K线画线）SKILL.md allowed-tools 增补 + 提示词强制「走势/形态/买卖点判断先检索知识库，引用原样保留 citation（可溯源）」——引用而非全文注入；四个独立执行器同样注入工具，未注入时（开关关闭）不得编造引用。
- 定时 AI 任务经**服务层直调**检索服务（不经工具层，依赖方向既有规范）。

## 10. API 面（wire camelCase + shared/types/kb.ts 单一真相源；query snake_case）

### 10.1 管理侧（`api/v1/admin/kb.py`，`get_current_admin_user` + `record_audit`）

| 端点 | 说明 |
|------|------|
| `GET/POST/PATCH/DELETE /admin/kb/sources` | 知识库 CRUD（DELETE 软删 + 24h 恢复窗口，审计 `kb.source.delete`） |
| `GET /admin/kb/sources/{id}/media` | 素材列表：集号/时长·页数/大小/状态/知识点数/索引态 |
| `POST /admin/kb/sources/{id}/media/init` | 批量建行 + 预签名 PUT（`[{fileName, relativePath, size, hash}]`） |
| `POST /admin/kb/media/{id}/uploaded` | HEAD 核对 + 哈希去重 + 状态流转 |
| `PATCH/DELETE /admin/kb/media/{id}` | 集号/标题调整；单素材删除（同软删路径） |
| `POST /admin/kb/cost-estimate` | `{sourceId, mediaIds, kinds}` → 分项预估（时长/页数/图片数 × unit_prices） |
| `POST /admin/kb/sources/{id}/confirm-cost` | `{mediaIds, kind}` → `awaiting_cost → queued`（审计 `kb.cost.confirm`） |
| `GET/PUT /admin/kb/sources/{id}/transcript/{mediaId}` | 文稿编辑器读写（PUT 触发脏传播） |
| `GET /admin/kb/sources/{id}/images?media_id=&page=&page_size=` | 图片资产列表（书嵌图 + 课程关键帧，缩略图代理签名，§4.1/§5.1） |
| `GET/POST /admin/kb/sources/{id}/chapters` | 目录树草稿查看 / 发布（`draft → published`，审计） |
| `GET /admin/kb/sources/{id}/points?status=&page=&pageSize=` | 审核队列（含计数）；`POST /admin/kb/sources/{id}/points`（人工新增）；`PATCH /admin/kb/points/{id}`（修订）；`POST /admin/kb/points/{id}/approve|reject`；`POST /admin/kb/points/merge` |
| `POST /admin/kb/sources/{id}/reindex` / `POST /admin/kb/index/rebuild-embedding` | 全量置脏重物化 / embedding 模型切换全量重嵌（审计） |
| `GET/PUT /admin/kb/settings` | 热词/并发/分段/单价/top_k/白名单 + 四模型角色槽位（`embedding_config_id`/`clean_model_id`/`extract_model_id`/`vision_model_id`，均为 `llm_config` 条目引用；PUT 时校验条目存在且 purpose 匹配） |
| `GET /admin/kb/usage?sourceId=&from=&to=` | 建库用量聚合：`user_token_usage` 按 `kb_*` feature × source（detail 上下文）汇出 token 明细与估算成本，叠加 ASR 时长（`process_meta`）× `unit_prices.asrPerHour`——预估 vs 实际对照 |

### 10.2 消费侧（`api/v1/kb.py`，权限 = admin 或白名单）

| 端点 | 说明 |
|------|------|
| `GET /kb/search?q=&sourceId=&chapterPath=&pointType=&kind=` | 混合检索（§7.2 形状） |
| `GET /kb/sources` | 消费侧知识库最小投影（enabled + 未软删；403 兼作未授权提示） |
| `GET /kb/sources/{id}/chapters` | 发布态章节树导航 |
| `GET /kb/sources/{id}/points?chapterPath=&page=&pageSize=` | 章节卡片清单（浏览路径：全集确定性排序 episode_no/start_ms/page_start + 分页，读 PG 真相源；未知章节 422） |
| `POST /kb/media/{id}/playback-token` | 一次性短时效凭证（≤30min，绑定用户+素材；携带 prev/next 集 id 与书 pageCount） |
| `GET /kb/stream/{mediaId}?token=` | 视频代理流（Range 必须，206 透传） |
| `GET /kb/books/{mediaId}/pages/{no}?token=` | 书页位图（服务端水印烧录） |
| `GET /kb/media/{id}/subtitles.vtt` | 字幕轨生成（apiClient Bearer） |
| `GET /kb/images/{id}/original-url` | 图片原图短时效预签名（≤15min） |

二期追加：`POST /admin/kb/optimizations`（触发建议单）、`GET /admin/kb/optimizations`、`POST /admin/kb/optimizations/{id}/apply|reject`。

## 11. 前端

```
web/src/pages/Admin/KnowledgeBase/
├── index.tsx              # antd Tabs 六页签（路由 /admin/knowledge-base）
├── SourcesTab.tsx         # 知识库列表 + 新建/编辑弹层 + 存储大小 + 删除（armed 两步，复刻社媒先例）
├── IngestTab.tsx          # KB 切换 seg + 文件夹拖拽上传区（webkitdirectory）+ 上传队列（进度/暂停重试）+ 流水线表
├── CostEstimateModal.tsx  # 分项预估 + 确认（费用闸门 UI）
├── ReviewTab.tsx          # 左章节树（草稿确认/拖拽）右知识卡片队列（通过/修订/驳回/合并）
├── SearchTab.tsx          # 搜索 + 三类命中 + 命中直达播放器/阅读器（consumerSources 注入兼供消费页复用）
├── SettingsTab.tsx        # 热词/并发/分段/单价/白名单 + 模型角色配置（清洗/抽取/视觉/嵌入四槽位，候选项按 llm_config purpose 过滤）+ 建库用量面板（token 分项 + 预估 vs 实际）
├── KnowledgePlayer.tsx    # 播放器（区间高亮/倍速记忆/断点续播/键盘/字幕联动/token 自动刷新）
├── BookReader.tsx         # 阅读器（按页位图/跳页/缩放/命中页标注/断点续读）
├── playerUtils.ts         # 播放器/阅读器共享纯函数（VTT 解析/时钟格式/token 刷新余量）
└── UploadQueue.tsx        # 直传队列（预签名 PUT 并发 + 进度 + 断点重试）

web/src/pages/KnowledgeSearch/
└── index.tsx              # 消费页 /kb（consumer sources + 403 自解释；内嵌 SearchTab）
```

- `web/src/api/kb.ts` + `adminKb.ts`（ENDPOINTS + apiClient 惯例）；`shared/types/kb.ts`（`ApiKbSource`/`ApiKbMedia`/`ApiKbPoint`/`ApiKbSearchResult`/`ApiKbPlaybackToken`…）+ `shared/api/endpoints.ts` 注册；`hooks/queryKeys.ts` 加 `kb` namespace。
- 上传进度的文件夹结构解析用 `DataTransferItem.webkitGetAsEntry` 递归（拖拽）+ `<input webkitdirectory>`（点选）兜底；直传进度不进 React state 高频渲染（ref + requestAnimationFrame 节流）。
- 播放器时间交互遵循前端时间约定：视频时间码为集内相对时间，与日期/时区无关。

## 12. 后端模块布局与部署

```
backend/app/services/kb/
├── source_service.py        # 知识库 CRUD、存储聚合、软删级联
├── media_service.py         # 上传 init/uploaded、分片会话（建/续/弃）、哈希去重、集号管理
├── cleanup_service.py       # kb-cleanup 执行体：过窗软删物理清除、超龄会话 abort、deep 孤儿扫描
├── transcribe_service.py    # 分片切分、asr-1.0 调用、断点缓存、清洗（clean_model_id）、用量入 meta
├── book_parse_service.py    # PyMuPDF 文本层抽取、段落归并、嵌入图片抽取（无 OCR 通道）
├── image_describe_service.py# VLM 图像理解（run_structured vision + vision_model_id）
├── vision_pipeline.py       # 关键帧选帧纯函数（showinfo 解析/三路信号融合/时间窗合并/aHash 去重/配额裁剪）
├── vision_service.py        # 课程关键帧通道（选帧零 LLM 阶段 + 描述计费阶段，vision_at 幂等）
├── extract_service.py       # 章节推断 + 知识点抽取（窗口化、三层幻觉防线、extract_model_id）
├── index_service.py         # 脏扫描、批量 embedding 物化（kb_embed 记账）、维度前置校验
├── search_service.py        # PG 双路召回（trgm 词面 + halfvec 向量）+ 服务层 RRF + 水合（唯一检索入口，Agent 工具复用）
├── playback_service.py      # 凭证、代理流、页渲染水印、异常审计
├── embedding_client.py      # OpenAI 兼容 /v1/embeddings 小客户端（embedding_config_id）
├── usage_service.py         # 建库用量聚合（user_token_usage kb_* 分项 + ASR 时长 × 单价 → 预估 vs 实际）
└── settings_service.py      # 域参数 + 模型角色槽位解析与 purpose 校验
backend/app/repositories/kb/{source_repository, media_repository, segment_repository, point_repository, image_repository}.py
backend/app/models/kb.py    # 5 表 + kb_settings
backend/app/schemas/kb.py   # LLM 抽取契约（裸 BaseModel 全 required）+ CamelModel wire
backend/app/constants/kb.py # source_type/point_type/process_status/doc_kind 枚举、Redis 键模板（凭证/锁）
backend/app/api/v1/admin/kb.py · api/v1/kb.py
backend/collector/runtime/specs/kb.py + backend/collector/spiders/kb_*.py   # §13 六任务
```

- 依赖方向：services/kb 不顶层导入 `app.agent.tools/skills/runtime`（`run_structured` 函数内延迟导入）；spider 薄壳委托服务层（`kb_transcribe.py` 等）。
- **新增依赖**：`pymupdf`（文本层抽取 + 嵌入图片对象）、`pypdfium2`（页位图按需渲染，无重依赖）、`Pillow`（水印合成）、`pgvector`（SQLAlchemy `HALFVEC` 列类型，纯轮子）。全部为轻量纯轮子，主镜像（web-api/collector）构建只增体积不增容器——**compose 零新增服务**。
- ES 容器已全栈退役（2026-09-21）：研报/财报全文改存 `file_metadata.content`（pypdf 抽取 + GIN trgm），`search_vector_kb` 走 PG 词面检索，健康探针摘除 ES 项；KB 检索此前已迁 PG 单库（halfvec HNSW + pg_trgm + RRF）。es 容器与 9200 端口从 compose 移除（曾因 `0.0.0.0:9200` 暴露 + 弱凭据被外部客户端清空索引，2026-09-20 事故加速退役）。

## 13. 任务注册与调度（F-MON 全覆盖）

| TaskSpec | data_type | 渠道 | queue / 时限 | seed cron（北京时间） | 扫描驱动 |
|----------|-----------|------|--------------|----------------------|----------|
| `kb-transcribe` | `kb_transcribe` | internal | heavy / 3600s·4200s | `*/5 * * * *` | `kb_media.process_status='queued'` 且 kind video/audio |
| `kb-book-parse` | `kb_book_parse` | internal | batch | `*/10 * * * *` | queued 且 kind book（文本层解析分钟级，无重算力） |
| `kb-extract` | `kb_extract` | internal | batch | `*/10 * * * *` | done 且未抽取素材 + 目录树待推断源 |
| `kb-vision` | `kb_vision` | internal | batch | `*/10 * * * *` | done 且 `vision_at` 空的 video 素材（选帧）+ `pending` 图片行（描述，§4.1 两阶段） |
| `kb-index` | `kb_index` | internal | batch | `*/5 * * * *` | `embedding_dirty` 三类行（嵌入物化） |
| `kb-cleanup` | `kb_cleanup` | internal | batch | `*/30 * * * *` | `deleted_at` 过 24h 恢复窗口的源/素材 |

- 无待处理行 = SKIPPED 正常态（F-MON 不误报）；ASR 渠道失败/疑似扫描版素材 = FAILED 显式归因。六条任务中转写/抽取/视觉/索引按 `(task, internal)` 参与 F-MON 健康判定（cleanup 等维护类不参与健康统计）。
- 管理端「立即执行」复用采集管理手动补跑通道；admin 触发类操作（费用确认/树发布/重建索引）改状态后可手动 run-now 提速，不另建端点。

## 14. 成本治理（模型角色可配 + 用量台账统一口径）

- **前置预估**：`POST /admin/kb/cost-estimate` 按 `kb_settings.unit_prices` 计算（时长×asrPerHour、图片数×vlmPerImage、清洗/抽取按字符数估 token、嵌入按字符数估 token），分项展示 → 确认后才 `queued`（状态门，非端点逻辑）。**asr-1.0 单价未公开刊例**：上线前控制台试跑 1 集核实并回填 `unit_prices`，预估失真即告警项。
- **统一用量台账**（原则 8）：清洗/抽取/视觉（run_structured → UsageMeterCallback）与嵌入（embedding_client 手动 enqueue）全部入 `user_token_usage`（system 维度 + `kb_*` feature + detail 上下文），**真实 usage 优先**；ASR 时长型用量落 `kb_media.process_meta`。`GET /admin/kb/usage` 按知识库/特征聚合 token 与估算成本，与前置预估对照（预估 vs 实际），模型切换后成本结构变化可追溯。
- **模型成本可调**：四角色后台可换——清洗/抽取在 M2.5/M3 同价位间切换、VLM 可插拔、embedding 可换供应商（蓝绿重建）——切档后新调用按新条目计量，台账按 model_name 分列不混淆。
- **不重复消耗**：文稿未变不重转（分片缓存）、书未变不重解析（file_hash）、知识点未变不重嵌（dirty 标记）、清洗与抽取结果随素材状态缓存。

## 15. 验证

- 单测（`backend/tests/unit/`）：抽取 Schema「无默认值」钉死；定位越界 clamp/丢弃；excerpt 模糊校验与 `needs_review` 标记；related 回链剔除；哈希去重 409；状态机流转（awaiting_cost 不可跳过）；费用预估公式；模型角色槽位解析与 purpose 不匹配校验（clean/extract/vision/embedding 四路）+ `run_structured(config_id=)` 透传；用量台账（kb_* feature 落账、embedding 客户端手动记账、usage 聚合端点分项正确）；RRF 融合黄金样本（固定两路排名断言融合序）；dirty 传播（文稿编辑→分段脏、publish→点脏、驳回→检索失效）；物化任务（增量拾取/写入清脏同事务/维度护栏 SKIPPED）；检索双路 SQL（词面 trgm 候选 + 向量 `<=>` 排序 + 行内过滤与水合同口径）；凭证矩阵（无 token/过期/错配 401、无 Range 400 + 审计事件）；页渲染水印合成；WebVTT 生成；存储聚合与软删清理路径；扫描版素材（文本层缺失）FAILED 归因。
- 前端测试：上传队列（目录结构解析/进度/重试）；播放器控制（倍速记忆/断点续播/A-B/键盘/字幕联动 seek）；阅读器跳页；检索三类命中渲染；wire 类型同构。
- docker 栈走查（对照需求 §9 验收表）：批量上传→预估→确认→转写进度→抽取→审核发布→检索命中 seek ±2s→字幕联动→书页跳页高亮→图片命中→防盗（网络面板无直链、凭证过期被拒、无 Range 拒绝+审计、水印可见）→embedding 切换无缝→删库级联清理。
- 质量门：backend `uv run mypy app/`、`ruff check .`、`pytest -m unit`；web typecheck / lint / test / build。

## 16. 风险与边界

1. **PG 检索能力边界**：`pg_trgm` 词面路无词频/IDF 权重语义（非 BM25）——术语/子串查询靠词面路精确命中，长自然语言靠向量语义路承载，RRF 融合对两种形态均不落空；HNSW 为近似召回（ef_search 可调），语料 ≤1 万行召回损失可忽略；`halfvec` fp16 存储对余弦排序精度的影响在该量级下不可测。
2. **asr-1.0 商务不确定**：单价未刊例、无热词参数——控制台试跑核价前置；渠道可插拔（`asr_channel_config`，阿里 Paraformer ≈¥0.29/小时为备选），管线与状态机不变。
3. **扫描版素材混入**：文字版单通道后，扫描版 PDF（无文本层）解析即 FAILED 显式归因「疑似扫描版」，不产低质数据；扫描版 OCR 能力后置（出现真实扫描素材再立项，届时再评估 MinerU 类方案）。
4. **模型角色误配置**：槽位指向不存在/停用条目或 purpose 不符会让管线任务批量 FAILED——settings 保存与启动时双重校验 + 明确报错；台账按 model_name 分列，切档成本影响可追溯。
5. **抽取质量**：LLM 幻觉三层防线（定位校验/摘录匹配/关联剔除）+ 人工审核兜底；抽取窗口化控制上下文长度，Schema 全 required 防字段省略。
6. **防盗边界**：代理 + 凭证 + 审计 + 水印组合显著抬高批量盗取成本；录屏/翻拍不可根除（需求明示边界），溯源靠水印。
7. **embedding API 外部依赖**：物化任务失败显式退避；检索页 embedding 失败走词面路降级（`degraded` 标记）；模型切换走全量重嵌（行级覆写）不中断检索。
8. **语料规模上限**：当前量级（≤1 万行）PG 单库为最优解；涨至数十万级或需要词法权重排序（BM25 语义）时再评估专门检索引擎——检索服务双路接口不变，底座可替换。
9. **单渠道 ASR 单点**：与 F-SOC 抖音渠道同理，靠 F-MON 快速告警 + 显式归因，不做静默 fallback。
10. **关键帧漏采与视觉成本**：场景检测阈值对无切换讲解型课程可能漏帧——文稿引导采样路兜底；VLM 按张计费靠单集配额（~120 张）+ describe 退避（≥3 终态）封顶，费用入台账可对账；帧图为检索交付物，M3 整视频理解仅记二期评估备选。

## 17. 后续文档索引

- [02-data-collection.md](./02-data-collection.md) — internal 任务体系与 F-MON 健康监测
- [04-ai-agent.md](./04-ai-agent.md) — `run_structured` 结构化输出、skill 资产与工具注入
- [03-data-storage.md](./03-data-storage.md) — 表命名约定与幂等迁移双写规范
- [06-deployment.md](./06-deployment.md) — compose 服务组织（本设计零新增容器）
- [10-account-quota.md](./10-account-quota.md) — `user_token_usage` 台账与 UsageMeter 计量（kb_* feature 复用）
