# 知识库架构设计（温成趋势理论 · F-KB）

> 闭环：后台登记多知识库（课程/电子书）→ 文件夹批量直传 COS → 课程 ASR 分片转写（句级时间戳）/ 电子书文本层解析（PyMuPDF + 嵌入图片资产）→ LLM 章节推断 + 知识点抽取 → 人工审核发布 → ES `kb-knowledge` 混合索引（BM25 + dense_vector，客户端 RRF）→ 内部检索页（片段播放器/阅读器，代理 + 短时效凭证防盗）→ Agent 运行时引用与技能优化建议单（审核后生效）。
> 需求：[docs/requirement/04-knowledge-base-requirement.md](../requirement/04-knowledge-base-requirement.md)（F-KB V1.1）· 原型：[docs/prototypes/knowledge-base.html](../prototypes/knowledge-base.html)
> 调研基线（2026-09）：ES 部署为 **8.13 Basic**（原生 RRF retriever 需 8.16 GA + Enterprise 授权）；MiniMax ASR 仅 `asr-1.0`（≤500s/50MB/次，无热词参数，句级时间戳可用，单价未公开刊例）；MiniMax M3 为多模态对话模型、非识别模型，定位在转写后清洗与知识抽取。**电子书确认为文字版 PDF**（2026-09-18 拍板）：单通道文本层解析，扫描版 OCR 后置（出现扫描版素材再立项）。

## 1. 设计原则

1. **PG 是唯一真相源，ES 是可随时重建的派生索引**：知识点/分段/图片资产的文本、状态、定位全部在 PG；ES 只存检索投影（文本 + 向量 + 过滤字段 + 定位）。文稿编辑、知识点修订通过 `embedding_dirty` 脏标记传播，索引任务增量拾取——任何索引损坏或模型切换都可从 PG 全量重建。
2. **语义流与定位流解耦**：embedding 输入是清洗后的纯文本，时间戳/页码/集号只走元数据字段不进向量——检索质量与定位精度（±2s 目标）互不牵制，这是音频 RAG 的定式。
3. **一套索引、三类文档**：知识卡片（point）/ 内容分段（segment）/ 图片资产（image）同入 `kb-knowledge` 索引，`doc_kind` 字段区分。卡片命中给「概念级答案」，分段命中给「原文取证」，图片命中给「文字搜图」；命中后回链 PG 水合完整定位。语料量级 ≤1 万文档，单索引绰绰有余。
4. **建库任务是状态驱动的 internal worker，费用确认是状态门**：HTTP 端点只改状态与预估，四类任务（转写/解析/抽取/索引）扫描 `pending`/`dirty` 行增量推进（最终一致，非实时）；素材 `awaiting_cost` 状态不经管理员确认不会变 `queued`——成本闸门内建于状态机，不依赖端点自觉。
5. **复用不重建，零新增部署容器**：collector internal 任务体系、`run_structured`（全字段 required 铁律）、`asr_channel_config`（F-SOC 已建，渠道凭据复用）、MinIO 封装（私有桶 + 预签名）、`UsageMeterCallback` 系统维度计量、CamelModel wire、redis_lock、F-MON——全部沿用；电子书文字版单通道后（2026-09-18 拍板）不引入任何解析 sidecar，主镜像只添轻量 Python 依赖（pymupdf / pypdfium2 / Pillow）。
6. **检索底座维持 ES 单一检索面**（已评审拍板）：BM25 与 dense_vector 同索引双查询，融合在服务层实现（8.13 Basic 无原生 RRF retriever，客户端融合 <30 行，未来升级 ES/许可可平移到原生 `rrf` retriever）。**pgvector 记为备选不落地**——中文 BM25 在 PG 侧依赖半维护分词扩展（zhparser/pg_jieba），词法路反正离不开 ES，向量拆去 PG 只会造成文档双存储双同步；若未来语料涨至数十万级或去 ES 化再评估。
7. **防盗是纵深组合**：私有桶直链永不透出 + 后端鉴权代理（视频 Range 透传 / 书页按需位图渲染）+ 一次性短时效凭证（≤30min，绑定用户与素材）+ 异常拉取审计 + 水印（书页服务端烧录、播放画面前端角标）——技术目标是显著抬高批量盗取成本，不承诺防录屏（需求边界）。
8. **模型角色全部后台配置，用量统一台账**：管线四类模型角色——清洗（chat）/ 知识抽取（chat）/ 图片理解（vision）/ 向量嵌入（embedding）——全部落 `llm_config` 配置条目，`kb_settings` 持角色槽位引用，admin 可随成本与质量切换，代码不硬编码模型名；全部 LLM/embedding 调用计入既有 `user_token_usage` 台账（`kb_*` feature + 上下文 detail），ASR 时长型用量入 `kb_media.process_meta`——建库成本随时可评估（§14）。

## 2. 数据模型

迁移 `docker/database/migrations/20260918_knowledge_base.sql`（幂等）+ `init-scripts/01-schema.sql` 双写（[03-data-storage](./03-data-storage.md) 规范）；SQLAlchemy 模型落 `backend/app/models/kb.py`（单数表名 + `kb_` 前缀，`Mapped` 2.0 风格，审计字段走 `app.core.clock.utc_now`）。

| 表 | 键与约束 | 说明 |
|----|----------|------|
| `kb_source` | `source_type CHECK ('course','book')`；`deleted_at`（软删） | `name`/`author`（讲师·作者，按类型展示标签）/`description`/`enabled`；`chapter_tree JSONB`（`{draft, published}` 两棵树，节点 `{id, title, children}`，节点 id 稳定）；`storage_bytes BIGINT`（COS 登记字节数聚合）、`pending_cleanup_bytes`（异步清理未完成量） |
| `kb_media` | uq `(source_id, episode_no)` WHERE episode_no IS NOT NULL；uq `(source_id, file_hash)`（去重）；idx `(source_id, process_status)` | `media_kind CHECK ('video','audio','book')`；`episode_no INT NULL`（课程集号）、`title`、`file_name`、`cos_key`、`file_size`、`file_hash`；`duration_seconds`/`page_count`（按类型）；`process_status CHECK ('uploaded','awaiting_cost','queued','processing','done','failed')` + `process_error`；`process_meta JSONB`（用量对账：provider/model/audio_seconds/chunk_count/est_cost…）；`edited_at TIMESTAMPTZ NULL`（文稿人工编辑时刻，脏传播源） |
| `kb_transcript_segment` | uq `(media_id, seq_no)`；idx `(source_id, embedding_dirty)` | 泛化内容分段：课程 `start_ms`/`end_ms`（句级时间码），电子书 `page_start`/`page_end`（跨页段落合并后为页区间）；`text`；`embedding_dirty BOOLEAN DEFAULT true`（新建/编辑即脏，索引任务增量拾取） |
| `kb_knowledge_point` | idx `(source_id, status)`、`(embedding_dirty)` | `point_type CHECK ('concept','theorem','method','discipline','case')`；`title`/`body`（正文，保留讲师表述）/`term_definition NULL`/`applicable_scene NULL`/`excerpt`（原文摘录）；定位：`media_id FK` + `start_ms`/`end_ms`（课程）或 `page_start`/`page_end`（书）；`related_ids JSONB`；`chapter_path`（发布树节点 id 串）；`status CHECK ('draft','published','rejected')`；`needs_review BOOLEAN`（excerpt 校验未过的显式标记）；`review_note`/`reviewed_by`/`reviewed_at` |
| `kb_image_asset` | idx `(source_id, embedding_dirty)` | 书中图片资产（需求「随书登记」的落表细化——逐张生命周期与 ES 同步需要独立行）：`media_id FK CASCADE`、`page_no`、`bbox JSONB NULL`、`cos_key`（原图）、`thumb_cos_key`（缩略图）、`text_in_image`/`caption`/`vision_description`、`describe_status CHECK ('pending','processing','done','failed')` |
| `kb_settings` | 单行 | `hotwords JSONB`（金融热词表，注入清洗 prompt）、`segment_max_seconds INT DEFAULT 30`、`asr_concurrency INT DEFAULT 2`、`top_k INT DEFAULT 8`、`unit_prices JSONB`（`{asrPerHour, vlmPerImage}` 参考单价，费用预估用）、`authorized_user_ids JSONB`（知识库授权白名单；admin 隐含授权）；**模型角色槽位**（均 FK `llm_config.id`，admin 后台可切换）：`embedding_config_id`（用途=embedding）、`clean_model_id`（转写清洗，chat）、`extract_model_id`（章节推断+知识抽取，chat）、`vision_model_id`（图片理解，vision） |

连带两处既有表扩展：

- `llm_config` 增列 `purpose VARCHAR(16) DEFAULT 'chat' CHECK IN ('chat','embedding','vision')`（既有行不动，默认 chat）。管线代码不硬编码模型名，一律经 `kb_settings` 角色槽位解析到 `llm_config` 条目：LLM 三角色（清洗/抽取/视觉）走 `run_structured(..., config_id=<槽位指向的条目>)`（`run_structured` 增可选 `config_id` 参数，缺省回落现有 `resolve_llm`）；embedding 走该条目的 OpenAI 兼容 `/v1/embeddings`（bge-m3 1024 维，cosine），小客户端 `embedding_client.py` 直连，不经 langchain。后台启动/保存校验：四槽位必须已配置且条目 `purpose` 与角色匹配。
- `user_token_usage`（F-ACCT 已建）增列 `detail JSONB NULL`——建库用量复用这张台账而非新建表：`user_id NULL` = 系统维度（建库管线均为 system），`feature` 取 `kb_clean` / `kb_extract` / `kb_vision` / `kb_embed`，`detail` 存 `{sourceId, mediaId, taskRunId}` 上下文供按知识库聚合。embedding 客户端不经 langchain、无 UsageMeterCallback 回调，自行经 `usage_writer.enqueue` 记账；清洗/抽取/视觉走 `run_structured`，由 `UsageMeterCallback` 自动入账。ASR 时长型用量（非 token）继续落 `kb_media.process_meta`。

**ES 索引**：别名 `kb-knowledge` → 物理索引 `kb-knowledge-v{N}`（版本号与 embedding 模型指纹绑定，模型/维度变更必须新建物理索引）。mapping：`doc_kind`、`source_id`、`media_id`、`point_id`/`segment_id`/`image_id`、`point_type`、`chapter_path`、`title`、`text`（正文/分段文本/图片三文本合并）、`start_ms`/`end_ms`/`page_start`/`page_end`、`embedding dense_vector(dims, index: true, similarity: cosine)`、`indexed_at`。中文 BM25 分词是已知短板（8.13 标准分词对中文单字切分）：**推荐**自建 ES 薄镜像（`FROM elasticsearch:8.13.0` + infinilabs analysis-ik 插件）；不装则由 dense 语义路兜底，混合检索仍可用——列为部署可选项，不阻塞。

## 3. 素材接入与存储（F-KB-01）

```
文件夹拖拽（前端 webkitdirectory / DataTransferItem 保持目录结构）
  → POST /admin/kb/sources/{id}/media/init   # 批量建 draft 行 + 预签名 PUT（大文件直传 COS，前端并发分片）
  → 前端逐文件直传（进度入上传队列）→ POST .../media/{mid}/uploaded
       └─ 服务端 HEAD 对象核对：size/etag(md5=file_hash) → 去重校验（同库同哈希 409）→ 状态 uploaded
  → 管理员「预估建库费用」→ POST cost-estimate（时长/页数/图片数 × unit_prices）→ 确认 → awaiting_cost → queued
```

- 集号：按目录文件名自动编号，PATCH 可调（uq 约束兜底）；电子书按书册登记（同名书多版本 = 同 source 多 media 行）。
- 外部文稿导入（TXT/SRT）：init 时带 `transcriptOverride`，跳过 ASR 直接入分段（状态直通 done）。
- **存储大小**：上传/删除即时增减 `kb_source.storage_bytes`（登记字节数聚合）；异步清理未完成期间叠加 `pending_cleanup_bytes` 展示。
- **级联删除**：DELETE 为软删（`deleted_at`，列表即隐藏，24h 内可恢复）→ `kb-cleanup` internal 任务扫描过期软删行：COS 批量删（原件 + 派生分片缓存）→ 硬删行 → ES `delete_by_query(source_id)` → 清零 storage。删除知识库/素材/单集均走同一路径。

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
- 三文本（图内文字/图注/描述）合并入 ES image 文档 → query 命中返回缩略图（代理签名）+ 页码定位。

## 6. 章节推断与知识抽取审核（F-KB-03）

任务 `kb-extract`（internal）扫「转写/解析 done 且未抽取」的素材，服务层编排两步：

- **章节推断**（每知识源一次）：逐集大纲 `run_structured(EpisodeOutline, config_id=kb_settings.extract_model_id)` → 跨集合并单次调用生成目录树草稿 → 写 `kb_source.chapter_tree.draft`；审核工作台逐节点确认/修订/拖拽 → 发布为 `published`（节点 id 稳定，知识点 `chapter_path` 引用）。
- **知识点抽取**（按素材滑动窗口 ~10 分钟，窗口间带 1 段重叠上下文）：`run_structured(KbExtractionResult, config_id=kb_settings.extract_model_id)`，Schema `{points: [{title, body, point_type, term_definition, applicable_scene, excerpt, start_ms, end_ms, related_titles}]}`——**全字段 required、禁带默认值**（项目铁律，钉死单测）。幻觉防线三层：
  1. **定位校验**：时间码越界 clamp/丢弃（对齐 K 线画线锚点校验先例）；
  2. **摘录校验**：`excerpt` 须在素材分段中模糊命中（归一化后包含性判断），未过 → `needs_review=true` 交人工，不自动驳回；
  3. **关联校验**：`related_titles` 按标题回链同库知识点，未匹配剔除（sentiment 幻觉标的过滤同款）。
- **审核工作台**：draft → `published` / `rejected` / 修订后通过（仅 title/type/body/term/scene/chapter_path 可改，**原文摘录与定位不可改**）；支持人工新增、合并重复、维护关联。仅 `published` 进入索引（publish 置 `embedding_dirty`；驳回/删除同步删 ES 文档）。
- 抽取调用 Celery 路径 system 维度，费用经 UsageMeter 自动计量入台账（feature=kb_extract）；技能资产 `skills/kb-extract/{SKILL.md, prompt.yaml}`。

## 7. 索引构建与混合检索（F-KB-04）

### 7.1 增量索引（任务 `kb-index`，5 分钟心跳）

扫三类脏行批量推进（单轮上限 + embedding 批量 64/请求）：`point(status=published, dirty)` → 全字段文档；`segment(dirty)` → 文本文档；`image(describe done, dirty)` → 三文本合并文档；驳回/删除 → `delete` 文档。`kb_source.enabled=false` 或素材未 done 的不进索引。embedding 客户端不经 langchain，批量调用后按响应 `usage` 自行 `usage_writer.enqueue` 记账（feature=kb_embed，detail 带 source_id/media_id）。全量重建（admin 触发或模型切换）：全量置脏 + 索引任务消化，重建期间旧文档经别名继续可查。

### 7.2 检索服务（P95 < 500ms 预算主要花在 query embedding）

```
query ─→ embedding（bge-m3 1024d）─┬─ 查询 A：bool BM25（text + title，IK/标准分词，size=50）
   （query 向量 LRU 缓存可选）      └─ 查询 B：knn（k=20, num_candidates=200）     # ES 8.13 顶层 knn
        └─ 客户端 RRF 融合（k=60，仅看排名不需分数归一化）─→ doc_kind 分组
             ├─ point：top_k（默认 8，卡片加权）→ PG 水合（完整卡片 + 自带 excerpt + 定位）
             ├─ segment：原文取证按与命中卡片定位重叠就近挂载 + 独立命中列表
             └─ image：缩略图（短时效签名）+ 页码
   过滤器全链路透传：source_id / chapter_path 前缀 / point_type / doc_kind
```

- 课程命中附**前滚上下文**：播放起点 = `max(0, start_ms − 4000)`（需求 3~5s 口径）。
- ES 停机：检索页友好报错、Agent 工具返回明确降级文本——检索面故障不外溢到采集与既有页面。

### 7.3 embedding 模型切换（蓝绿，需求强制全量重建）

`kb_settings.embedding_config_id` 变更 → admin 触发重建任务：新建 `kb-knowledge-v{N+1}`（新 dims mapping，向量 `_reindex` 不能重嵌、必须从 PG 重算）→ 批量重嵌全量写入 → 抽样 30~50 条 query 对比新旧召回（recall@10）→ 校验过 → 单个 `_aliases` 原子操作 remove/add 切换 → 旧索引保留回滚一周后清理。**应用代码永远只见别名**。单用户小语料全量重建分钟级，无需双写队列。重嵌全量 token 消耗自然入台账（kb_embed），重建成本可事后核算。

## 8. 检索页、播放器与防盗（F-KB-05 + F-KB-09）

### 8.1 播放凭证与代理（安全面唯一入口）

```
POST /kb/media/{id}/playback-token   # 权限校验（admin / 白名单）→ Redis kb:playback:{token}={userId, mediaId} EX ≤1800
GET  /kb/stream/{mediaId}?token=     # 校验 token + 必须 Range 头 → MinIO get_object(offset/length) 206 透传（Content-Range/Accept-Ranges）
GET  /kb/books/{mediaId}/pages/{n}?token=  # pypdfium2 144DPI 按需渲染（干净页进程内 LRU）→ Pillow 叠用户水印 → PNG
GET  /kb/media/{id}/subtitles.vtt?token=   # 由 kb_transcript_segment 生成 WebVTT（字幕轨 + 点击跳转导航）
```

- **异常拉取拦截**：无 token / token 过期 / 不绑定 → 401 + 审计事件 `kb.security.denied`；视频流无 Range 头（整文件抓取特征）→ 400 + 审计；连续异常触发账号级告警（管理端可见，封禁为管理员决策）。
- **前端不接触 COS 直链**：缩略图、页面图、视频流全部经后端代理签名/代理输出；书页位图服务端烧录水印（干净页缓存与水印合成解耦，每请求一次轻量 composite）；播放画面叠加静态角标（用户名 + 日期，前端层，安全不依赖此层）。
- 播放器禁下载交互（`controlsList=nodownload`、禁右键）为提高门槛的前端手段。

### 8.2 页面与播放器能力（对照原型 knowledge-base.html）

- 检索 Tab：搜索框 + 章节树导航 + 三类命中（卡片高亮 / 原文摘录 / 图片缩略图+页码）；命中展开显示集数 + `hh:mm:ss–hh:mm:ss` 或页码区间。
- **KnowledgePlayer**：`<video src=/kb/stream/...?token>` + 自定义控制条——播放/暂停、进度条命中区间高亮（A/B 标记 + 循环）、倍速 0.5–2×（localStorage 记忆）、音量、全屏/画中画、键盘（Space/←→/↑↓）、断点续播（按 media 记忆）、上一集/下一集；**字幕联动**：WebVTT track + 当前端高亮 + 点击字幕句 seek（文稿即导航）；点击命中 → 自动 `seek(startMs − 前滚)`。
- **BookReader**：按页位图 + 页码跳转/前后页 + 命中页高亮标注 + 缩放；图片命中打开原图视图附页码上下文。
- 防盗边界声明（需求口径）：目标是抬高直接获取与批量盗取成本，录屏/翻拍以水印溯源震慑，不承诺根除。

## 9. Agent 消费（F-KB-06/07）

- **`search_knowledge_base(query, source?, chapter?, point_type?)`** 工具（二期）：注册进 `build_assistant_tools()`，**按会话用户权限注入**（admin / `kb_settings.authorized_user_ids` 白名单；普通用户会话不注册，内部知识不外泄）。返回压缩卡片集（标题 + 正文 + 类型 + 定位），token 预算受 top_k 约束；检索服务复用 §7.2（工具层薄封装）。降级：服务不可用返回明确错误文本，Agent 继续分析并声明未引用理论依据。
- 分析类技能（复盘/异动/涨停）SKILL.md allowed-tools 增补 + 提示词声明「涉及趋势与买卖点判断先检索知识库，结论注明引用知识点（可溯源集数/时间码）」——引用而非全文注入。
- 定时 AI 任务经**服务层直调**检索服务（不经工具层，依赖方向既有规范）。
- **技能优化建议单**（二期，表 `kb_optimization_suggestion`）：后台选「目标技能 × 知识源」手动触发 → 优化 Agent 读技能定义 + 检索知识点 → 产出修改点列表（原文/建议文/diff + 理由 + 引用定位）→ 审核队列「通过/修订后应用/驳回」→ custom 技能 version+1 直写生效；builtin 技能导出完整文件文本 + 变更说明交开发落代码库（运行时不改代码库文件）。同一技能存在未处理建议单时禁止发起新一轮；建议单全量留档可溯。

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
| `GET/POST /admin/kb/sources/{id}/chapters` | 目录树草稿查看 / 发布（`draft → published`，审计） |
| `GET /admin/kb/review/points?status=&chapterPath=` | 审核队列；`PATCH /admin/kb/points/{id}`（修订）；`POST /admin/kb/points/{id}/approve|reject`；`POST /admin/kb/points/merge` |
| `POST /admin/kb/sources/{id}/reindex` / `POST /admin/kb/index/rebuild-embedding` | 全量重建 / embedding 模型切换蓝绿（审计） |
| `GET/PUT /admin/kb/settings` | 热词/并发/分段/单价/top_k/白名单 + 四模型角色槽位（`embedding_config_id`/`clean_model_id`/`extract_model_id`/`vision_model_id`，均为 `llm_config` 条目引用；PUT 时校验条目存在且 purpose 匹配） |
| `GET /admin/kb/usage?sourceId=&from=&to=` | 建库用量聚合：`user_token_usage` 按 `kb_*` feature × source（detail 上下文）汇出 token 明细与估算成本，叠加 ASR 时长（`process_meta`）× `unit_prices.asrPerHour`——预估 vs 实际对照 |

### 10.2 消费侧（`api/v1/kb.py`，权限 = admin 或白名单）

| 端点 | 说明 |
|------|------|
| `GET /kb/search?q=&sourceId=&chapterPath=&pointType=&kind=` | 混合检索（§7.2 形状） |
| `GET /kb/sources/{id}/chapters` | 发布态章节树导航 |
| `POST /kb/media/{id}/playback-token` | 一次性短时效凭证（≤30min，绑定用户+素材） |
| `GET /kb/stream/{mediaId}?token=` | 视频代理流（Range 必须，206 透传） |
| `GET /kb/books/{mediaId}/pages/{no}?token=` | 书页位图（服务端水印烧录） |
| `GET /kb/media/{id}/subtitles.vtt?token=` | 字幕轨生成 |

二期追加：`POST /admin/kb/optimizations`（触发建议单）、`GET /admin/kb/optimizations`、`POST /admin/kb/optimizations/{id}/apply|reject`。

## 11. 前端

```
web/src/pages/Admin/KnowledgeBase/
├── index.tsx              # antd Tabs 五页签（路由 /admin/knowledge-base）
├── SourcesTab.tsx         # 知识库列表 + 新建/编辑弹层 + 存储大小 + 删除（armed 两步，复刻社媒先例）
├── IngestTab.tsx          # KB 切换 seg + 文件夹拖拽上传区（webkitdirectory）+ 上传队列（进度/暂停重试）+ 流水线表
├── CostEstimateModal.tsx  # 分项预估 + 确认（费用闸门 UI）
├── ReviewTab.tsx          # 左章节树（草稿确认/拖拽）右知识卡片队列（通过/修订/驳回/合并）
├── SearchTab.tsx          # 搜索 + 三类命中 + KnowledgePlayer + BookReader
├── SettingsTab.tsx        # 热词/并发/分段/单价/白名单 + 模型角色配置（清洗/抽取/视觉/嵌入四槽位，候选项按 llm_config purpose 过滤）+ 建库用量面板（token 分项 + 预估 vs 实际）
└── components/
    ├── KnowledgePlayer.tsx # 播放器（区间高亮/倍速记忆/断点续播/A-B/键盘/画中画/字幕联动）
    ├── BookReader.tsx      # 阅读器（按页位图/跳页/缩放/命中高亮）
    └── UploadQueue.tsx     # 直传队列（预签名 PUT 并发 + 进度 + 断点重试）
```

- `web/src/api/kb.ts` + `adminKb.ts`（ENDPOINTS + apiClient 惯例）；`shared/types/kb.ts`（`ApiKbSource`/`ApiKbMedia`/`ApiKbPoint`/`ApiKbSearchResult`/`ApiKbPlaybackToken`…）+ `shared/api/endpoints.ts` 注册；`hooks/queryKeys.ts` 加 `kb` namespace。
- 上传进度的文件夹结构解析用 `DataTransferItem.webkitGetAsEntry` 递归（拖拽）+ `<input webkitdirectory>`（点选）兜底；直传进度不进 React state 高频渲染（ref + requestAnimationFrame 节流）。
- 播放器时间交互遵循前端时间约定：视频时间码为集内相对时间，与日期/时区无关。

## 12. 后端模块布局与部署

```
backend/app/services/kb/
├── source_service.py        # 知识库 CRUD、存储聚合、软删级联
├── media_service.py         # 上传 init/uploaded、哈希去重、集号管理
├── transcribe_service.py    # 分片切分、asr-1.0 调用、断点缓存、清洗（clean_model_id）、用量入 meta
├── book_parse_service.py    # PyMuPDF 文本层抽取、段落归并、嵌入图片抽取（无 OCR 通道）
├── image_describe_service.py# VLM 图像理解（run_structured vision + vision_model_id）
├── extract_service.py       # 章节推断 + 知识点抽取（窗口化、三层幻觉防线、extract_model_id）
├── index_service.py         # 脏扫描、批量 embedding（kb_embed 记账）、ES 写删、别名蓝绿
├── search_service.py        # 双路召回 + 客户端 RRF + PG 水合（唯一检索入口，Agent 工具复用）
├── playback_service.py      # 凭证、代理流、页渲染水印、异常审计
├── embedding_client.py      # OpenAI 兼容 /v1/embeddings 小客户端（embedding_config_id）
├── usage_service.py         # 建库用量聚合（user_token_usage kb_* 分项 + ASR 时长 × 单价 → 预估 vs 实际）
└── settings_service.py      # 域参数 + 模型角色槽位解析与 purpose 校验
backend/app/repositories/kb/{source_repository, media_repository, segment_repository, point_repository, image_repository}.py
backend/app/models/kb.py    # 5 表 + kb_settings
backend/app/schemas/kb.py   # LLM 抽取契约（裸 BaseModel 全 required）+ CamelModel wire
backend/app/constants/kb.py # source_type/point_type/process_status/doc_kind 枚举、Redis 键模板（凭证/锁）
backend/app/api/v1/admin/kb.py · api/v1/kb.py
backend/collector/runtime/specs/kb.py + backend/collector/spiders/kb_*.py   # §13 五任务
```

- 依赖方向：services/kb 不顶层导入 `app.agent.tools/skills/runtime`（`run_structured` 函数内延迟导入）；spider 薄壳委托服务层（`kb_transcribe.py` 等）。
- **新增依赖**：`pymupdf`（文本层抽取 + 嵌入图片对象）、`pypdfium2`（页位图按需渲染，无重依赖）、`Pillow`（水印合成）。全部为轻量纯轮子，主镜像（web-api/collector）构建只增体积不增容器——**compose 零新增服务**。
- ES 薄镜像（可选增强）：`FROM elasticsearch:8.13.0` + analysis-ik 插件，compose 换 image 构建层；不装则标准分词 + dense 路兜底。
- 客户端锁定 `elasticsearch[async]>=8.13,<9` 不动；kNN 用 8.13 顶层 `knn` 查询（retriever API 是 8.16+，不升级不用）。

## 13. 任务注册与调度（F-MON 全覆盖）

| TaskSpec | data_type | 渠道 | queue / 时限 | seed cron（北京时间） | 扫描驱动 |
|----------|-----------|------|--------------|----------------------|----------|
| `kb-transcribe` | `kb_transcribe` | internal | heavy / 3600s·4200s | `*/5 * * * *` | `kb_media.process_status='queued'` 且 kind video/audio |
| `kb-book-parse` | `kb_book_parse` | internal | batch | `*/10 * * * *` | queued 且 kind book（文本层解析分钟级，无重算力） |
| `kb-extract` | `ai_kb_extract` | internal | batch | `*/10 * * * *` | done 且未抽取素材 + 目录树待推断源 |
| `kb-index` | `kb_index` | internal | batch | `*/5 * * * *` | `embedding_dirty` 三类行 + 删除文档 |
| `kb-cleanup` | `kb_cleanup` | internal | batch | `*/30 * * * *` | `deleted_at` 过 24h 恢复窗口的源/素材 |

- 无待处理行 = SKIPPED 正常态（F-MON 不误报）；ASR 渠道失败/疑似扫描版素材 = FAILED 显式归因。五条 `(task, internal)` 注册进 F-MON 判定表。
- 管理端「立即执行」复用采集管理手动补跑通道；admin 触发类操作（费用确认/树发布/重建索引）改状态后可手动 run-now 提速，不另建端点。

## 14. 成本治理（模型角色可配 + 用量台账统一口径）

- **前置预估**：`POST /admin/kb/cost-estimate` 按 `kb_settings.unit_prices` 计算（时长×asrPerHour、图片数×vlmPerImage、清洗/抽取按字符数估 token、嵌入按字符数估 token），分项展示 → 确认后才 `queued`（状态门，非端点逻辑）。**asr-1.0 单价未公开刊例**：上线前控制台试跑 1 集核实并回填 `unit_prices`，预估失真即告警项。
- **统一用量台账**（原则 8）：清洗/抽取/视觉（run_structured → UsageMeterCallback）与嵌入（embedding_client 手动 enqueue）全部入 `user_token_usage`（system 维度 + `kb_*` feature + detail 上下文），**真实 usage 优先**；ASR 时长型用量落 `kb_media.process_meta`。`GET /admin/kb/usage` 按知识库/特征聚合 token 与估算成本，与前置预估对照（预估 vs 实际），模型切换后成本结构变化可追溯。
- **模型成本可调**：四角色后台可换——清洗/抽取在 M2.5/M3 同价位间切换、VLM 可插拔、embedding 可换供应商（蓝绿重建）——切档后新调用按新条目计量，台账按 model_name 分列不混淆。
- **不重复消耗**：文稿未变不重转（分片缓存）、书未变不重解析（file_hash）、知识点未变不重嵌（dirty 标记）、清洗与抽取结果随素材状态缓存。

## 15. 验证

- 单测（`backend/tests/unit/`）：抽取 Schema「无默认值」钉死；定位越界 clamp/丢弃；excerpt 模糊校验与 `needs_review` 标记；related 回链剔除；哈希去重 409；状态机流转（awaiting_cost 不可跳过）；费用预估公式；模型角色槽位解析与 purpose 不匹配校验（clean/extract/vision/embedding 四路）+ `run_structured(config_id=)` 透传；用量台账（kb_* feature 落账、embedding 客户端手动记账、usage 聚合端点分项正确）；RRF 融合黄金样本（固定两路排名断言融合序）；dirty 传播（文稿编辑→分段脏、publish→点脏、驳回→删文档）；别名蓝绿切换（创建→校验→原子切换→回滚路径）；凭证矩阵（无 token/过期/错配 401、无 Range 400 + 审计事件）；页渲染水印合成；WebVTT 生成；存储聚合与软删清理路径；扫描版素材（文本层缺失）FAILED 归因。
- 前端测试：上传队列（目录结构解析/进度/重试）；播放器控制（倍速记忆/断点续播/A-B/键盘/字幕联动 seek）；阅读器跳页；检索三类命中渲染；wire 类型同构。
- docker 栈走查（对照需求 §9 验收表）：批量上传→预估→确认→转写进度→抽取→审核发布→检索命中 seek ±2s→字幕联动→书页跳页高亮→图片命中→防盗（网络面板无直链、凭证过期被拒、无 Range 拒绝+审计、水印可见）→embedding 切换无缝→删库级联清理。
- 质量门：backend `uv run mypy app/`、`ruff check .`、`pytest -m unit`；web typecheck / lint / test / build。

## 16. 风险与边界

1. **ES 8.13 Basic 能力边界**：原生 RRF retriever 与 `linear` 融合不可用（8.16 GA + Enterprise 授权）——客户端融合 <30 行且参数透明（k=60、窗口 50），升级 ES 后平移；中文 BM25 标准分词弱是检索质量的主要变量，IK 插件薄镜像是低成本高收益增强项（列为部署决策点，混合检索可兜底）。
2. **asr-1.0 商务不确定**：单价未刊例、无热词参数——控制台试跑核价前置；渠道可插拔（`asr_channel_config`，阿里 Paraformer ≈¥0.29/小时为备选），管线与状态机不变。
3. **扫描版素材混入**：文字版单通道后，扫描版 PDF（无文本层）解析即 FAILED 显式归因「疑似扫描版」，不产低质数据；扫描版 OCR 能力后置（出现真实扫描素材再立项，届时再评估 MinerU 类方案）。
4. **模型角色误配置**：槽位指向不存在/停用条目或 purpose 不符会让管线任务批量 FAILED——settings 保存与启动时双重校验 + 明确报错；台账按 model_name 分列，切档成本影响可追溯。
5. **抽取质量**：LLM 幻觉三层防线（定位校验/摘录匹配/关联剔除）+ 人工审核兜底；抽取窗口化控制上下文长度，Schema 全 required 防字段省略。
6. **防盗边界**：代理 + 凭证 + 审计 + 水印组合显著抬高批量盗取成本；录屏/翻拍不可根除（需求明示边界），溯源靠水印。
7. **embedding API 外部依赖**：索引任务失败显式退避；检索页友好报错；模型切换走蓝绿不中断检索。
8. **pgvector 备选**（不落地）：若语料涨至数十万级或未来去 ES 化，PG 侧向量（同库事务、切换原子）是第一备选——当前中文词法必须 ES，双存储纯增负担。
9. **单渠道 ASR 单点**：与 F-SOC 抖音渠道同理，靠 F-MON 快速告警 + 显式归因，不做静默 fallback。

## 17. 后续文档索引

- [02-data-collection.md](./02-data-collection.md) — internal 任务体系与 F-MON 健康监测
- [04-ai-agent.md](./04-ai-agent.md) — `run_structured` 结构化输出、skill 资产与工具注入
- [03-data-storage.md](./03-data-storage.md) — 表命名约定与幂等迁移双写规范
- [06-deployment.md](./06-deployment.md) — compose 服务组织（本设计零新增容器）
- [10-account-quota.md](./10-account-quota.md) — `user_token_usage` 台账与 UsageMeter 计量（kb_* feature 复用）
