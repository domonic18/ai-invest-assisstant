# 知识库（F-KB）开发计划

> 基线：[arch 12](../arch/12-knowledge-base.md)（2026-09-18 定稿，含模型角色配置与 token 台账二次增补）+ [需求 04](../requirement/04-knowledge-base-requirement.md) V1.1 + [原型](../prototypes/knowledge-base.html)。
> 批次独立开发、独立验收；合计约 18.5 人日（一期 15.5 + 二期 3）。
> 跨批次红线（全程有效）：抽取 Schema 全字段 required 禁默认值；wire camelCase + shared/types 单一真相源、query 参数 snake_case；幂等 SQL 迁移 + init-scripts 双写；业务日期走 `app.core.clock`；`services/kb` 不顶层导入 `app.agent.*`（`run_structured` 函数内延迟导入）；模型调用真实 usage 优先入 `user_token_usage` 台账。

## 0. 迭代映射（排期归 development-plan）

| 迭代 | 批次 | 交付物 | 预估 |
|------|------|--------|------|
| 迭代 12 · F-KB 一期上 | A 底座 → B 素材接入与转写 → C 电子书解析 | 素材进得来（直传/去重/费用闸门）、课程转写与书解析跑得通、文稿与分段可见 | ~5.5 人日 |
| 迭代 13 · F-KB 一期下（一期验收） | D 抽取审核 → E 索引检索 → F 播放器防盗 → G 用量与收口 | 建库全链路闭环：审核发布→混合检索→精准回看/跳页/搜图→防盗→用量可评估 | ~8 人日 |
| 迭代 13 · 批次 I（D 后中插） | I 视频关键帧通道 | 视频画面信息入知识库：三路信号选帧 → 去重入库 → VLM 描述计费 → 图片资产可见（检索消费留批次 E/F） | ~2 人日 |
| 迭代 14 · F-KB 二期 | H Agent 消费 | `search_knowledge_base` 权限注入 + 技能优化建议闭环 | ~3 人日 |

## 1. 批次 A · 底座：数据模型、迁移、模型角色与设置（~1.5 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| A1 | 迁移与模型 | `docker/database/migrations/20260918_knowledge_base.sql`（幂等）：`kb_source`/`kb_media`/`kb_transcript_segment`/`kb_knowledge_point`/`kb_image_asset`/`kb_settings` 六表 + `llm_config.purpose` CHECK ('chat','embedding','vision') + `user_token_usage.detail JSONB NULL`；同步 `init-scripts/01-schema.sql`；`app/models/kb.py`（Mapped 2.0 风格）+ `models/__init__.py` 导出 |
| A2 | 常量与契约 | `app/constants/kb.py`（source_type/media_kind/process_status/point_type/doc_kind 枚举、Redis 键模板）；`app/schemas/kb.py`：LLM 抽取契约（`KbExtractionResult`/`EpisodeOutline`/`ImageUnderstanding`，裸 BaseModel 全 required）+ CamelModel wire 模型；「Schema 无默认值」钉死单测 |
| A3 | 模型角色与设置服务 | `services/kb/settings_service.py`：域参数 + 四角色槽位（`embedding_config_id`/`clean_model_id`/`extract_model_id`/`vision_model_id`）解析与 purpose 校验（保存/读取双侧）；`agent/runtime/structured.py` `run_structured` 增可选 `config_id`（缺省回落 `resolve_llm`，透传单测）；`embedding_client.py` 骨架（OpenAI 兼容 `/v1/embeddings`） |
| A4 | 设置 API 与 shared | `GET/PUT /admin/kb/settings`（PUT 校验槽位条目存在且 purpose 匹配）；`shared/types/kb.ts` + `shared/api/endpoints.ts` 注册 + `cd shared && npm run build`；`hooks/queryKeys.ts` 加 `kb` namespace；SettingsTab 基础表单（四角色选择器，候选项按 purpose 过滤） |

验收：mypy/pytest/ruff 绿；purpose 错配被拦（四个角色各一条负例）；`run_structured(config_id=)` 单测透传正确。

## 2. 批次 B · 素材接入与课程转写（F-KB-01/02，~2.5 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| B1 | 知识库与素材服务 | `source_service.py`（CRUD、`storage_bytes` 聚合、软删 + `pending_cleanup_bytes`）+ `media_service.py`（init 批量建行 + 预签名 PUT、uploaded HEAD 核对、`(source_id, file_hash)` 去重 409、集号 uq）；admin API：sources CRUD / media init·uploaded·PATCH·DELETE |
| B2 | 费用闸门 | `POST /admin/kb/cost-estimate`（时长/图片数 × `unit_prices` + 清洗/抽取按字符数估 token，分项展示）+ `POST .../confirm-cost`（`awaiting_cost → queued`，审计）；状态机单测（不可跳过闸门） |
| B3 | 转写服务 | `transcribe_service.py`：ffmpeg 16kHz 单声道 → silencedetect 切分 ≤480s → asr-1.0（复用 `asr_channel_config`，并发=`asr_concurrency`）→ 分片缓存 COS derived 前缀（断点续跑）→ 句级合并 → 清洗（`run_structured(config_id=clean_model_id)`，热词入 prompt）→ 落分段 + `process_meta`；渠道失败显式 FAILED 归因不重试烧钱 |
| B4 | 任务接线 | `collector/runtime/specs/kb.py` 加 `kb-transcribe`（heavy 3600/4200）+ `spiders/kb_transcribe.py` 薄壳 + seed cron `*/5 * * * *` + F-MON 判定表登记 `(kb_transcribe, internal)` |
| B5 | 文稿编辑与前端 | `GET/PUT /admin/kb/sources/{id}/transcript/{mediaId}`（PUT 触发 `edited_at` + 分段置脏）；前端 `SourcesTab`/`IngestTab`（webkitdirectory 目录解析 + 直传进度 ref+rAF 节流）/`UploadQueue`/`CostEstimateModal`/文稿编辑器 |

验收：上传→预估→确认→转写进度→文稿编辑→脏传播全链路；中断重跑不重转（分片缓存命中）；同哈希 409；ASR 渠道失败 FAILED 归因可见。

> **勘误（2026-09-20，预估费用全 0）**：时长三处都漏——init 请求契约有 `durationSeconds` 但前端从不填、转写探针只算不存、预估恰在转写前发生 → `duration_seconds` 全库 NULL。修法三层：前端登记时 `<video>` 元数据本地读时长（读不出如 mkv 留空）、转写/选帧探针探到即回写、存量 68 行经 MinIO 内部端点（`svc.client` 而非公网 `_presign_client`，容器内不可达 `localhost:9002`）ffprobe 一次性补齐。

## 3. 批次 C · 电子书解析与图片资产（F-KB-10，~1.5 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| C1 | 解析服务 | `book_parse_service.py`：PyMuPDF 逐页文本层抽取（逐页字符数写 `process_meta`）→ 跨页段落归并 → 分段（page 区间）→ `get_images` 抽嵌入图（原图/缩略图传 COS）→ `kb_image_asset` 行；文本层缺失 = FAILED 归因「疑似扫描版，不收」 |
| C2 | 图片理解 | `image_describe_service.py`：`run_structured(ImageUnderstanding, images=[图], vision=True, config_id=vision_model_id)`，三文本（图中文字/图注/描述）全 required；prompt 附前后页文本 |
| C3 | 任务接线 | `kb-book-parse`（batch）+ `spiders/kb_book_parse.py` + seed cron `*/10 * * * *` + F-MON 登记 |

验收：文字版书解析出页级分段 + 图片资产（缩略图可见）；扫描版样本 FAILED 归因；VLM token 入台账（feature=kb_vision）。

## 4. 批次 D · 章节推断与知识抽取审核（F-KB-03，~2 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| D1 | 抽取服务 | `extract_service.py`：章节推断（逐集 `EpisodeOutline` → 跨集合并草稿写 `chapter_tree.draft`）+ 滑窗 ~10min 抽取（窗口间 1 段重叠）；三层防线：定位越界 clamp/丢弃、`excerpt` 模糊命中不过→`needs_review`、`related_titles` 回链剔除 |
| D2 | 任务接线 | `kb-extract`（batch）+ `spiders/kb_extract.py` + seed cron `*/10 * * * *` + F-MON 登记 |
| D3 | 审核 API 与工作台 | 目录树 draft 查看/发布（审计）、`GET /admin/kb/review/points`、`PATCH points/{id}`（仅 title/type/body/term/scene/chapter_path 可改，摘录与定位不可改）、approve/reject/merge；前端 `ReviewTab`（左章节树确认/拖拽，右卡片队列） |

验收：抽取字段无缺失（Schema 钉死单测）；三层防线各自负例通过；仅 published 进索引的流转正确（publish 置脏单测）。

> **交付记录（2026-09-19，迭代 13 一期下起点）**：D1/D2/D3 完成——`extract_pipeline.py` 纯函数（开窗/clamp/excerpt 归一化命中/related 回链/去重/位置 id）+ `extract_service.py`（章节两步推断 + 滑窗抽取 + `extractAttempts≥3` 防毒）+ `kb-extract` 任务（batch 1800/2100，`*/10`）+ 审核服务与 8 条 admin 路由 + 前端 `ReviewTab`（章节树编辑发布 / 卡片通过·修订后通过·驳回·合并·人工新增，draft 可勾选合并，needsReview 琥珀标；2026-09-20 补批量通过——`POST /points/approve-batch` 单事务逐张审计，已发布/不存在幂等跳过）。偏差：知识点列表挂 `/sources/{id}/points`（与 media 同构，弃草稿期 `/review/points` 字面）；章节树编辑为「改名/增删/上下移」未做拖拽（KISS，两级树拖拽收益低）；needsReview 计数为展示非过滤维度。`embedding_dirty` 置脏流转已钉死单测（approve 必置脏、原 published 驳回置脏），索引构建与消费留批次 E；播放片段按钮留批次 F。端到端验证期修复两处存量集成 bug：① `transcribe_service` 转写 done 误置 `extracted_at`（抽取幂等键，致扫描永空转，已删置位并重置存量）；② `user_token_usage` 特征 CHECK 约束在本库为旧命名 `chk_usage_feature`，KB 迁移按现名 DROP 静默空转致 kb_* 计量被拒——迁移补历史名兼容 DROP（本地已修，`kb_extract` 台账实测入账）。本地实跑 16 集 27 分钟：348 草稿（needsReview 207 / 定位缺失 3 / related 回链 341）、章节树 7 顶层章、调度回归 transcribe/cleanup 正常 SKIPPED。

## 5. 批次 E · 索引构建与混合检索（F-KB-04，~2 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| E1 | embedding 客户端 | `embedding_client.py` 完成：批量 64/请求、按响应 usage `usage_writer.enqueue`（feature=kb_embed，detail 带上下文） |
| E2 | 索引服务 | `index_service.py`：三类脏行扫描批量推进 + 驳回/删除删文档；ES mapping（`kb-knowledge-v{N}` 别名蓝绿，dims 与模型指纹绑定）+ 全量重建（admin 触发 / 模型切换：新建→重嵌→recall@10 抽样→原子切换→旧索引保留一周）；`kb-index`（batch）+ spider + seed `*/5` + F-MON 登记 |
| E3 | 检索服务 | `search_service.py`：bool BM25（size=50）+ 8.13 顶层 knn（k=20/num_candidates=200）→ 客户端 RRF（k=60，窗口 50）→ doc_kind 分组 → PG 水合；过滤器全链路透传；课程命中前滚 4s；ES 停机降级文本 |
| E4 | 检索 API 与页面骨架 | `GET /kb/search` + `GET /kb/sources/{id}/chapters`（权限 = admin/白名单）；`SearchTab` 三类命中列表（卡片高亮/原文摘录/缩略图+页码）——播放器接入留批次 F |

验收：RRF 融合黄金样本；dirty 传播三路单测；蓝绿切换全路径（含回滚）；`/reindex` 与 `rebuild-embedding` 审计。

> **提前交付（2026-09-20，图片资产治理工作台）**：批次 E 范围内的图片治理面提前落地——`kb_image_asset.index_excluded` 列（迁移 `20260921b` 幂等）+ 管理台「图片资产」Tab（`ImagesTab`：集数/描述状态筛选、24/页分页、缩略图预签名）+ `POST /admin/kb/images/{id}/redescribe`（清空描述重置 pending，仅限视频帧，书嵌图 409）与 `PATCH /admin/kb/images/{id}`（索引排除开关，变更才审计），shared 契约与 hooks 同步。两操作均置 `embedding_dirty`，索引消化仍归本批次 E2/E3。E2E 实测：排除幂等（重复开不重复审计）、帧 567 重新描述经 kb-vision 全链路回 done、路由 401 门禁。

## 6. 批次 F · 检索页播放器、阅读器与防盗（F-KB-05/09，~3 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| F1 | 播放与防盗服务 | `playback_service.py`：`POST /kb/media/{id}/playback-token`（Redis ≤1800s 绑定用户+素材）；`/kb/stream`（token + Range 必须 → 206 透传）；`/kb/books/{id}/pages/{n}`（pypdfium2 144DPI + Pillow 水印，干净页 LRU）；`/kb/media/{id}/subtitles.vtt`；异常拉取审计（`kb.security.denied`）+ 连续异常告警 |
| F2 | 播放器组件 | `KnowledgePlayer.tsx`：命中区间进度条高亮 + 自动 seek（前滚）、A-B 循环、倍速 0.5–2× 记忆、断点续播、键盘、画中画、上一/下一集、WebVTT 字幕联动（当前句高亮 + 点句 seek） |
| F3 | 阅读器与集成 | `BookReader.tsx`（按页位图/跳页/缩放/命中高亮/图片原图上下文）；SearchTab 接入播放器与阅读器完成命中直达 |

验收：凭证矩阵（无 token/过期/错配 401、无 Range 400 + 审计事件）；网络面板无 COS 直链；命中 seek ±2s、字幕联动点句跳转；书页水印可见；对照原型走查。

## 7. 批次 G · 用量看板、清理与一期收口（~1 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| G1 | 用量聚合 | `usage_service.py` + `GET /admin/kb/usage?sourceId=&from=&to=`：台账 `kb_*` 分项 token × 模型单价 + ASR 时长（process_meta）× asrPerHour，预估 vs 实际对照；SettingsTab 用量面板 |
| G2 | 清理任务 | `kb-cleanup`（batch）+ spider + seed `*/30` + F-MON 登记：扫过 24h 恢复窗的软删行 → COS 批删 → 硬删 → ES delete_by_query → storage 清零（已提前接线 2026-09-19：过窗软删物理清除 + 超龄分片会话 abort + 每日孤儿对象扫描；ES delete_by_query 随检索投影接线批次补齐，维护类任务不参与 F-MON 健康统计） |
| G3 | 一期收口 | F-MON 五任务判定复核（SKIPPED=正常态）；docker 栈全链路走查（对照需求 §9 验收表逐行）；质量门全绿 |

验收：用量分项与台账一致（抽样对账）；删库级联清理后检索无残留；需求 §9 一期行全部通过。

## 8. 批次 I · 课程视频关键帧通道（~2 人日）

> 2026-09-19 追加（批次 D 验收后评审拍板，arch 12 §4.1）：转写仅消费音频，视频画面的盘面讲解（画线/指标/走势）不进知识库。轻量关键帧通道补齐该维度，帧图本身是检索交付物（搜图缩略图 + 时间码跳播）。MiniMax M3 整视频理解 token 成本 ~1fps 等效、远高于按张计费，记为二期评估备选（批次 H 后评估，不预建）。

| # | 任务 | 内容与改法 |
|---|------|-----------|
| I1 | 迁移与模型 | `docker/database/migrations/20260919_kb_vision.sql`（幂等）：`kb_image_asset.page_no` DROP NOT NULL + 增 `start_ms`/`end_ms BIGINT NULL` + `describe_attempts INT NOT NULL DEFAULT 0`；`kb_media` 增 `vision_at TIMESTAMPTZ NULL`；seed 三件套（`kb_vision_scan` internal `*/10`，仿 20260921_kb_extract_task.sql 三段式）；init-scripts 双写；`models/kb.py` 同步 |
| I2 | 选帧管线 | `vision_pipeline.py` 纯函数（无 IO）：showinfo `pts_time` 解析；三路信号融合——场景切换（`select='gt(scene,0.3)'`）/ 定长 60s 兜底 / 文稿视觉指涉句正则取句中点（消费 `kb_transcript_segment` 文本：你看/如图/这条线/这个下降通道/这个中枢…）；时间窗合并（<5s 保留 1，优先级 文稿>场景>定长）；aHash（ffmpeg 16×16 灰度 rawvideo，纯 Python 汉明距离 ≤5 去重，不引 Pillow）；单集配额 120 张按优先级裁剪 |
| I3 | 视觉服务 | `vision_service.py`：`redis_lock("kb:vision")` → `resolve_role_model(session, "vision")` 槽位校验（未配置归因返回）→ 阶段一选帧：扫 `process_status='done' AND vision_at IS NULL AND deleted_at IS NULL` 且 kind=video → ffmpeg 抽帧 → 去重 → COS `kb/derived/{media_id}/frames/{start_ms:012d}.jpg`（原图+缩略）→ `kb_image_asset` 行（pending）→ `vision_at=now()`（幂等键，重跑不重抽）；阶段二描述：扫 pending 行 `run_structured(ImageUnderstanding, images=[帧], vision=True, config_id=…)`（函数内延迟导入红线 + `meter_scope(None, FEATURE_KB_VISION)`），prompt 附前后句文稿；失败 `describe_attempts+1`，≥3 终态 failed |
| I4 | 任务与 API | `kb-vision` TaskSpec（batch 1800/2100）+ `spiders/kb_vision.py` 薄壳 + `core/constants.py` 域映射（F-MON 判定 DB-driven 随 seed）；`GET /admin/kb/sources/{id}/images?media_id=&page=&page_size=`（行 + 缩略图预签名 URL，query snake_case）+ shared types/endpoints（`cd shared && npm run build`）；前端不做 UI（批次 E 检索消费） |

验收：真实视频抽帧入库（时间码正确、近重复被滤、单集配额生效）；VLM 描述入台账（kb_vision 分项）；describe 失败退避 ≥3 终态；重跑不重抽（vision_at 幂等）；admin images 端点契约；转写/抽取/清理调度回归正常。

> **交付记录（2026-09-19）**：I1–I4 完成——迁移 `20260919_kb_vision.sql`（幂等，含 seed 三件套）+ `vision_pipeline.py` 纯函数（场景解析/视觉指涉句中点/时间窗合并/aHash/配额裁剪）+ `vision_service.py` 两阶段（选帧零 LLM → `vision_at` 幂等记账；描述按张计费 `meter_scope(FEATURE_KB_VISION)` + 前后句文稿上下文，`describe_attempts≥3` 终态）+ `kb-vision` 任务（batch 1800/2100，`*/10`）+ `GET /admin/kb/sources/{id}/images`（缩略图 1h 预签名，query snake_case）+ shared 契约；前端零 UI（批次 E 检索消费）。端到端验证期修复两处集成 bug：① `_detect_scenes` 必须加 `-an -sn -dn` 丢非视频流，否则 null muxer 缓冲音轨以 `Too many packets buffered` 整体失败；② `session.rollback()` 使循环携带的 ORM 实例全部过期，属性访问逃出 per-media 容错致整轮 FAILED——vision_service 两阶段与 extract_service `_extract_points`（同型存量）统一改「循环前预捕获纯元组 + 迭代内按 id 重取」。本地实跑 16 集 19 分钟视频：567 帧入库（单集 ~29 帧，远低于 120 配额；aHash 近重复过滤生效；帧图课件文字清晰可读实检通过），描述首批 20/20 成功入台账（kb_vision 25,745 tokens/20 行），存量 547 帧由 `*/10` 调度按 20/轮消化；images 端点未认证 401 门禁实测 + 契约单测钉死；调度回归 transcribe/extract/cleanup 正常 SKIPPED。

## 9. 批次 H · 二期 Agent 消费（F-KB-06/07，~3 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| H1 | 检索工具 | `search_knowledge_base(query, source?, chapter?, point_type?)` 注册进 `build_assistant_tools()`，按会话权限注入（admin / 白名单，普通用户不注册）；压缩卡片集受 top_k 约束；降级返回明确错误文本；分析类技能（复盘/异动/涨停）SKILL.md allowed-tools 增补 + 提示词声明引用规范 |
| H2 | 优化建议单 | `kb_optimization_suggestion` 表（迁移 + 双写）；后台选「目标技能 × 知识源」手动触发 → 优化 Agent 读技能定义 + 检索知识点 → 修改点列表（原文/建议文/diff + 理由 + 引用定位）；同技能存在未处理单时禁止新发 |
| H3 | 审核与应用 | 建议 API + 审核队列 UI（通过/修订后应用/驳回）；custom 技能 version+1 直写生效；builtin 导出完整文件文本 + 变更说明交开发落库（运行时不改代码库文件）；建议单全量留档 |

验收：普通用户会话无此工具（单测钉死）；未经审核的修改不生效；引用带集数/时间码可溯源。

## 10. 部署前置与运维项（随对应批次落地）

- **依赖**：`uv add pymupdf pypdfium2 Pillow`（批次 C/F）；**collector 镜像补 ffmpeg**（apt 层，批次 B 转写切分依赖）——Dockerfile 变更随批次 B 提交。
- **批次 I 零新增依赖**：ffmpeg 复用 collector 镜像既有层（批次 B 已补）；aHash 纯 Python 实现，不引 Pillow；抽帧走 subprocess。
- **compose 零新增服务**（零 sidecar）；ES IK 薄镜像为可选部署决策点，不阻塞（标准分词 + dense 路兜底）。
- **admin 前置配置**（联调前）：`llm_config` 登记 embedding（bge-m3 1024d）与 vision 条目并绑定四槽位；ASR 渠道复用 F-SOC `asr_channel_config`；asr-1.0 控制台试跑 1 集核价并回填 `unit_prices`（单价未公开刊例，预估失真告警项）。
- 客户端锁定 `elasticsearch[async]>=8.13,<9` 不动；kNN 用 8.13 顶层 `knn` 查询。

## 11. 风险速查（详见 arch 12 §16）

asr-1.0 单价未刊例（核价前置 + 渠道可插拔 Paraformer 兜底）｜扫描版混入（解析显式拒收）｜模型角色误配置（保存/启动双校验 + FAILED 归因）｜抽取幻觉（三层防线 + 人工审核）｜ES 8.13 无原生 RRF（客户端融合，升级可平移）｜防盗不承诺防录屏（水印溯源边界）｜关键帧漏采与视觉成本（三路信号互补 + 单集配额 + describe 退避 + 台账对账）。
