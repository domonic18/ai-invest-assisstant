# 知识库（F-KB）开发计划

> 基线：[arch 12](../arch/12-knowledge-base.md)（2026-09-20 修订定稿：检索去投影化 PG 单库；含模型角色配置与 token 台账二次增补）+ [需求 04](../requirement/04-knowledge-base-requirement.md) V1.1 + [原型](../prototypes/knowledge-base.html)。
> 批次独立开发、独立验收；合计约 20.5 人日（一期 17.5 + 二期 3）。
> 跨批次红线（全程有效）：抽取 Schema 全字段 required 禁默认值；wire camelCase + shared/types 单一真相源、query 参数 snake_case；幂等 SQL 迁移 + init-scripts 双写；业务日期走 `app.core.clock`；`services/kb` 不顶层导入 `app.agent.*`（`run_structured` 函数内延迟导入）；模型调用真实 usage 优先入 `user_token_usage` 台账。

## 0. 迭代映射（排期归 development-plan）

| 迭代 | 批次 | 交付物 | 预估 |
|------|------|--------|------|
| 迭代 12 · F-KB 一期上 | A 底座 → B 素材接入与转写 → C 电子书解析 | 素材进得来（直传/去重/费用闸门）、课程转写与书解析跑得通、文稿与分段可见 | ~5.5 人日 |
| 迭代 13 · F-KB 一期下（一期验收） | D 抽取审核 → E 索引检索 → F 播放器防盗 → G 用量与收口 | 建库全链路闭环：审核发布→混合检索→精准回看/跳页/搜图→防盗→用量可评估 | ~8.5 人日 |
| 迭代 13 · 批次 I（D 后中插） | I 视频关键帧通道 | 视频画面信息入知识库：三路信号选帧 → 去重入库 → VLM 描述计费 → 图片资产可见（检索消费留批次 E/F） | ~2 人日 |
| 迭代 13 · 批次 J（E 后中插） | J 检索去投影化 | PG 单库混合检索（halfvec HNSW + pg_trgm + 服务层 RRF），KB 链路摘除 ES 投影与投影管理机械 | ~2 人日 |
| 迭代 13 · 批次 K（J 后追加） | K 全系统去 ES | 研报/财报全文入 PG（`file_metadata.content` + trgm），`search_vector_kb` 改纯 PG，ES 容器/依赖/探针全退役 | ~1 人日 |
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

> **交付记录（2026-09-20，E1/E2）**：E1 完成——`embed_batched`（64/请求分片顺序拼接）与 `discover_dims`（实测维度，ES mapping dims 与模型指纹绑定不硬编码）；E2 完成——`index_service.py` 增量（三类 `embedding_dirty` 扫描：published 点/done 分段/done 未排除图片 upsert，rejected·排除·软删素材子行删文档；单轮各类 500 限量，余量下轮续跑）+ bootstrap（首跑建 `kb-knowledge-v1` 挂别名）+ 指纹校验（`index.meta.kb_fingerprint` = config_id:模型:维度，不符 SKIPPED 提示重建）+ 蓝绿重建（`force_rebuild`：新建 v{N+1} 全量灌入 → refresh 后 count 对账 → 原子切别名 → 按 `updated_at < started` 清脏（重建期间新编辑留待下轮）→ 超 7 天无别名旧版本清理）；重建入口复用 `POST /admin/collector/tasks/kb-index/run`（run_params=force_rebuild，不另设路由）。删除兜底三路接线：素材/知识源软删与恢复置脏子行（`mark_media/source_children_dirty`，下轮增删文档）、kb-cleanup 硬删前 `delete_docs_for_media/source`（best-effort）、转写重灌前 `delete_segment_docs`（旧行脏标随行消失）。`kb-index` TaskSpec（batch 1800/2100，run_params=force_rebuild）+ spider 薄壳（SKIPPED 五态：锁忙/未配模型/指纹不符/无脏行/成功）+ 迁移 `20260920_kb_index_task.sql`（seed 三件套 + `*/5`）+ F-MON 域映射。单测 13 条（服务 7 + spider 6，ES/embedding 全 mock）。E2E 排障：embedding 网关条目 base_url 缺 `/v1`（200 返回网关 SPA HTML），本地栈已修 DB 并加固客户端非 JSON 响应显式报错；修正后管道全通，仅剩网关上游饱和 429（code 1113，外部阻塞），*/5 cron 自动重试，索引构建待网关恢复后自动完成。

> **交付记录（2026-09-20，E3/E4，批次 E 完结）**：E3 完成——`search_service.py` 双路召回（BM25 bool size=50 恒开 + 顶层 knn k=20/num_candidates=200，doc_kind/source_id/point_type 过滤器 term 子句全链路透传）→ 客户端 RRF（k=60，窗口 50，ES 8.13 Basic 无原生 RRF retriever）→ `_doc_key` 前缀分组（point-/seg-/img-）→ PG 水合防御（仅 published 点 + 活素材；图片 done 且未排除）；分类截断 points=top_k（默认 8）/segments=10/images=12。降级语义：ES 异常 → `degraded="es_unavailable"` 空结果不 500；embedding 未配置或调用失败 → 仅 BM25 + `degraded="embedding_unavailable"`。课程命中 `seek_ms = max(0, start_ms−4000)` 前滚；案例卡片关联帧（非书 + case 型 + 有 start：同素材命中窗 ±20s 内 done 未排除帧取 3，缩略图 1h 预签名）。章节过滤实现为水合后前缀过滤（仅点卡带章节亲和，segment/image 在章节过滤时整组不下发，ES 层过滤留优化）。E2 收尾补强：索引 keep 条件接 `source.enabled`（arch/12 §7.1，停用源不入索引）+ `update_source` 启停切换置脏子行。E4 完成——`GET /kb/search` 与 `GET /kb/sources/{id}/chapters`（消费路由 `api/v1/kb.py`，权限 = admin ∪ kb_settings.authorized_user_ids 白名单，router 级依赖；query snake_case，chapter_path 逗号拼接）+ shared 契约（ApiKbSearch* 五类型 + ApiKbMediaKind）+ 前端 `SearchTab`（章节树导航/来源选择/三类命中分段 Segmented/命中词 mark 高亮/RRF 分值/降级 Alert/案例帧缩略图/书籍页码），挂管理台第 6 个 Tab「知识检索」。偏差：SearchTab 暂居 admin 管理台（白名单用户独立消费页留批次 F/G 随播放器一起定位）；命中关联跳转/播放直达留批次 F。单测 22 条新增（检索服务 11 + API 5 + 索引 enabled 1 + SearchTab 6），后端 1999 全绿 mypy/ruff 干净，web typecheck/lint/348 单测全绿。E2E（真实 ES）仍阻塞于网关 429（code 1113），索引构建完成后待验。

> **E2E 交付（2026-09-20 下午，批次 E 验收闭环）**：embedding 切换智谱 BigModel（`embedding-3`，2048 维按量）后全链路实测打通——`kb-knowledge-v1` 首建 + 3449 文档（点 348 / 段 1994 / 图 1107），`/kb/search?q=支撑线` 双路无降级返回 8 卡 + 10 段 + 12 图，RRF 分值与 seek 前滚实测正确；章节树发布后消费端点 7 顶层章可见。E2E 期修复四项：① **base_url 归一化**（`app/utils/api_base.py` 单一真相源：剥尾斜杠 + 已知端点后缀 `/embeddings` `/chat/completions` `/speech_to_text` `/v1/messages`，ASR 专用再去 `/v1` 版本段）接入全部七处直连消费点（embedding/测试连接/LangChain 工厂/BYOK 保存与测试/ASR×3），根因是用户按厂商文档粘完整端点而客户端约定根地址自拼路径；② **测试连接 purpose 感知**：embedding 条目改打 `/embeddings` 并回报实测维度（此前一律 `/chat/completions` 致 404 误报），表单帮助文案同步；③ **ES 8.13 指纹机制纠偏**：`index.meta.*` 自定义设置已从 ES 移除（实测 400），改存 `mappings._meta.kb_fingerprint`（mock 单测盲区，真实 ES 才暴露）；④ **嵌入输入截断**：智谱 embedding-3 单条 ~3072 token 上限（实测 3000 字符 OK / 3500 FAIL，code 1210），ASR 退化重复段（4394 字）与截图 OCR 全量图注（5608 字）触发整批 400——`EmbeddingClient.embed()` 统一截断 2048 字符（BM25 侧 ES text 存全文不受影响）。开发态修复（审批置脏逻辑落地前发布的 348 published 点从未置脏，本地一次性 SQL 补齐后索引闭环；生产全新建库走列默认 TRUE + 审批置脏，无此状态——迁移库只承载 schema 演进与配套数据初始化，开发过程态修复不进迁移库，2026-09-20 评审定约）。遗留：348 点卡 `chapter_path` 全空（批次 D 两步推断的章节归属未回填到点，章节过滤暂无实际效果——批次 F 跟进）；1107 图文档中 40 张为排除/停描述后待下轮 tombstone 的余量。单测 +16（归一化 12 + 测试连接 3 + 截断 1），后端 2016 全绿。

## 6. 批次 F · 检索页播放器、阅读器与防盗（F-KB-05/09，~3.5 人日，2026-09-20 评审修订 MVP 分层）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| F0 | 遗留回填与消费页归属 | ① **管线健壮化重设计（2026-09-20 拍板，推翻原「chapter_path 回填」补偿方案）**：抽取生而归章——`kb_extract` 对未发布目录树的源不抽取（stats `awaitingChapterPublish`，SKIPPED 文案指引导发布），prompt 携带 published 树要求 LLM 输出 `chapter_path`（节点 id 链）+ `confidence`；升级门校验（`extract_pipeline.validate_points`）：时间码 clamp/缺失、**摘录锚定**（全文归一化拼接定位 + 省略号「……」分段顺序锚定，命中即以文稿原文替换 LLM 摘录——摘录是溯源锚点，替换后天然可信；无长度上限，任一段 miss 升级）、章节链修剪到合法前缀（悬空根升级）、置信度 ≠high 升级、case 卡叠加任何理由时显式标注；理由清单写 `review_note`（透明可审）。**自动发布门**：`kb_settings.auto_approve_points`（迁移 `20260920d`，默认 ON）开启时全绿卡直接 `published` + 置索引脏，有理由卡落 draft 升级人工；树重发布时 `publish_chapters` 修剪存量卡悬空引用（published 卡置脏）。测试环境删库重建端到端验证（保留 COS/文稿/图资产，重置章节树+点卡+extracted_at+ES 投影，PG 真相源自愈）。② 消费页落位：独立路由页 `/kb`（权限同 /kb router：admin ∪ 白名单），SearchTab/播放器/阅读器以消费页为主体（管理台 Tab 保留入口），白名单非 admin 用户全链路可用。③ 需求文档 04 V1.2 增补（关键帧通道入需求，批次 I 挂起决议） |
| F1 | 播放与防盗服务 | `playback_service.py`：`POST /kb/media/{id}/playback-token`（Redis ≤1800s 绑定用户+素材，**响应携带上一/下一集 id**——消费侧无 media 列表端点，admin 端点不外用）；`/kb/stream`（token + Range 必须 → 206 透传，**MinIOService 新增 ranged 读** offset/length，同步 SDK 走既有 to_thread 模式）；`/kb/books/{id}/pages/{n}`（pypdfium2 144DPI + Pillow 水印「用户名+日期」，**web 镜像补 CJK TTF 字体层**，干净页 LRU 定容量上限）；`/kb/media/{id}/subtitles.vtt`（**fetch 走同源 Cookie 鉴权**，query token 仅留给 `<video>` src）；异常拉取审计（`kb.security.denied`）+ Redis 滑动窗口计数，**管理端告警展示归批次 G**，F 不做 UI |
| F2 | 播放器组件（MVP） | `KnowledgePlayer.tsx`：命中区间进度条高亮 + 自动 seek（前滚）、倍速 0.5–2× 记忆（localStorage）、断点续播（localStorage 按 mediaId）、键盘（Space/←→/↑↓）、上一/下一集（token 响应相邻集）、WebVTT 字幕联动（当前句高亮 + 点句 seek）、**token 过期前自动刷新**（单集可超 1800s，防中途 401）。增强可延：A-B 循环、画中画 |
| F3 | 阅读器与集成（MVP） | `BookReader.tsx`（按页位图/跳页/缩放/命中定位：跳页 + 页角命中词标注）；SearchTab 接入播放器与阅读器完成命中直达；消费侧图片原图走 ≤15min 短时效预签名或代理端点（管理台 1h 口径不带入消费页）。增强可延：页内关键词 bbox 高亮（pypdfium2 textpage search） |

验收：凭证矩阵（无 token/过期/错配 401、无 Range 400 + 审计事件）；网络面板无 COS 直链；命中 seek ±2s、字幕联动点句跳转；书页水印可见（中文正常渲染）；长视频 token 刷新不断流；白名单用户（非 admin）消费页全链路实测；批次 E 遗留 40 张余量图片文档经下轮增量 tombstone 自愈复核；对照原型走查。

> **交付记录（2026-09-20 晚，F0① 完结）**：管线健壮化按重设计方案落地——生而归章（未发布树不抽取，`awaitingChapterPublish` 统计 + SKIPPED 文案指引导发布）、prompt 携带 published 树输出 `chapter_path`（id 链）+ `confidence`、升级门（时间码 clamp/缺失、摘录锚定、章节链修剪到合法前缀、置信度 ≠high、case 卡叠加显式标注）写 `review_note`，`kb_settings.auto_approve_points`（迁移 `20260920d`）全绿卡自动发布置索引脏、有理由卡升级人工，树重发布修剪存量卡悬空引用。**摘录锚定两轮数据驱动进化**：v1 段内归一化命中 → 省略号「……」分段顺序锚定（删节引用逐段原文、禁止回跳）→ 去掉跨度上限（全文归一化拼接 `find` + bisect 偏移映射回句级分段，长引用不升级），自动发布率 69% → 90%（中期）→ 86.8%（全量收敛）。**E2E 删库重建**（保留 COS/文稿/图资产，重置章节树+点卡+extracted_at+ES 投影）：36/36 素材抽取、721 卡（626 published 自动发布 86.8% / 95 升级人工——摘录未命中 42、medium 16、时间码无效 10 及组合叠加）、0 失败；章节树 10 顶层/62 叶；剩余未命中人工抽检确属模型改写（数字格式/措辞漂移），升级语义正确。
>
> **章节过滤召回缺陷（E2E 发现）系统性修复（浏览/搜索分层定型）**：症状 = 任意 `chapter_path` 过滤检索恒 0（节点 6.3 下 53 张 published 卡）；根因 = 过滤层错位——索引投影无章节维度，过滤只能在水合层做，而候选已被 top_k=8 截断（批次 E 小数据量下碰巧有效，「ES 层过滤留优化」实为召回缺陷）。方案 A 过滤下推 ES filter context：point 文档新增 `chapter_keys` 前缀键（`["2","2.5"]`→`["2","2/2.5"]`，term 精确命中表达根到节点前缀）+ 强制 `doc_kind=point`（原文/图片不参与章节过滤），水合层保留同口径投影滞后防御；**索引指纹纳入 mapping 版本**（`config_id:模型:维度:m{N}`，结构变更即失配 SKIPPED 拒写），存量索引走既有蓝绿机制重建 `kb-knowledge-v2`（626 点 + 1994 段 + 1127 图，95 张非 published 点卡 tombstone，refresh 后对账通过，指纹 `3:embedding-3:2048:m2`）。方案 B 浏览/搜索分离（行业标准「分类浏览走 DB、搜索走引擎」）：新增 `GET /kb/sources/{id}/points?chapter_path=&page=&page_size=`——PG `chapter_path @>` containment（位置 id 体系下含祖先链 ≡ 前缀匹配）+ GIN `jsonb_path_ops`（迁移 `20260920e`）+ `episode_no/start_ms/page_start` 确定性排序分页 + 发布树校验（未知章节 422，区别于搜索的静默空）。E2E：scoped 检索 0→8 卡（6/6.3 命中全部携带正确 chapter_path，`degraded=None`）、顶层章 `2` 过滤正常、无过滤回归不变（8 卡+10 段+12 图）、浏览 `total=53` 分页正确（30+23）、ES/PG 计数勾稽（term 6/6.3 = 53 = PG @>）。净增 5 单测（下推断言/水合防御/浏览服务与 API 契约），后端 2038 全绿 mypy/ruff 干净，web typecheck 通过。
>
> **交付记录（2026-09-21，F0②/F1/F2/F3，批次 F 完结）**：F1 完成——`playback_service.py` 四端点：`POST /kb/media/{id}/playback-token`（Redis one-shot ≤1800s 绑定 user+media，响应携带 prev/next 集 id 与书 pageCount）、`GET /kb/stream`（token + Range 必须 → 206 透传，MinIO ranged 读 offset/length）、`GET /kb/books/{id}/pages/{n}`（pypdfium2 144DPI 位图 + Pillow「用户名+日期」平铺 30° 水印烧录，干净页 LRU；web 镜像 `docker/web/Dockerfile` 已补 `fonts-wqy-zenhei` CJK 字体层，pyproject 补 pypdfium2/pillow）、`GET /kb/media/{id}/subtitles.vtt`（apiClient Bearer，query token 仅留给 `<video>` src）；异常拉取审计 `kb.security.denied` + Redis zset 滑动窗口计数（告警 UI 归批次 G）。F2 完成——`KnowledgePlayer.tsx` MVP 全项：命中区间进度条高亮 + 前滚 seek、倍速 0.5–2× localStorage 记忆（load()/换 src 重置 playbackRate 的规范坑已绕开——rate effect 挂 token 依赖）、断点续播按 mediaId、键盘 Space/←→/↑↓、上一/下一集（父层 mediaId 状态重挂载）、VTT 字幕联动（当前句高亮 + 点句 seek）、token 到期前 120s 自动刷新（保进度与播放态续播）；VTT 解析/时钟格式抽 `playerUtils.ts` 共享（react-refresh only-export-components 约束）。F3 完成——`BookReader.tsx`（页位图防拖拽/右键、跳页 InputNumber + 键盘、缩放 100–200% + 微调、命中页角标注 + 快捷 chips、断点续读——初始页首渲染前读定，规避持久化 effect 首拍回写覆盖保存值）、SearchTab 命中直达（卡片「播放定位/阅读定位」、分段「播放片段」走服务端 seekMs、图片「阅读此页/播放帧 + 原图」，播放器/阅读器互斥展开、同素材命中区间与命中页聚合并去重）、原图走 `GET /kb/images/{id}/original-url`（MinIO 预签名，常量 `KB_IMAGE_ORIGINAL_URL_TTL_SECONDS=900` ≤15min，管理台/消费页共用消费检索端点故缩略图 TTL 同步收紧 15min）、`GET /kb/sources` 消费侧最小投影（enabled+未软删，白名单用户不触 admin 端点）。F0② 完成——消费页 `/kb`（`KnowledgeSearchPage`：consumer sources useQuery + 403 自解释授权引导）+ 路由，SearchTab 经 admin Tab 与消费页双入口复用（`consumerSources` 注入即跳过 admin 源查询）。偏差：① 侧边栏「知识检索」入口随交付撤下（2026-09-21 用户反馈：功能暂仅管理台调试使用），`/kb` 路由与页面保留待后续启用；② 字幕 fetch 鉴权实态为 apiClient Bearer header（项目本无 Cookie 会话，原案「同源 Cookie」按实际鉴权机制落地，`<video>`/`<img>` 元素 src 仍走 query token）。质量门：后端 2079 单测全绿 + mypy 426 文件 + ruff 干净；web typecheck/lint/370 单测/build 全绿。E2E 期修复一处真冲突：`api/v1/kb.py` 原 router 级 `get_kb_authorized_user` 依赖要求 Bearer，与元素 src 凭证端点天然互斥（`<video>`/`<img>` src 无法携带 Authorization header → `/kb/stream`/`/kb/books` 携有效 token 仍 401）——改为逐路由声明依赖（其余六端点不变），stream/书页凭证即鉴权：凭证值带 `{userId}.` 前缀恢复过期/泄露场景的审计归属，完全不可解析的拒绝仅结构化日志（审计表 actor_id 非空约束不允许无主记录）；`render_book_page` 水印用户名改按凭证载荷回查 User（不可用即 401）。单测同步：凭证矩阵重写（前缀归属/无前缀不落审计/畸形载荷/素材错配）+ stream/书页「无 Bearer 放行」两条回归，后端 2083 全绿。**E2E 第二修复**：伪造 `{userId}.` 前缀指向不存在账号会触发审计表 `actor_id` FK 违约 500——凭证前缀是外部输入不可信，`_record_denial` 归属前先回查 User 存在，缺失同样走无主日志路径（新增单测钉死，后端 2084 全绿）。本地 docker 栈 E2E（2026-09-21）全绿：stream 无 Range 400 + 审计 / Range 206（Content-Range·video/mp4·100B·no-store）/ 伪造前缀·存在用户前缀·素材错配三种 401（审计行 actor 归属正确，无主拒绝仅结构化日志零落库）；subtitles.vtt text/vtt + 真实文稿 cue；混合检索 `q=支撑线` 8 卡+10 段+1 图无降级、segment seekMs 前滚 −4s 精确；原图预签名 expiresIn=900；容器内书页渲染 CJK 水印全页覆盖（wqy-zenhei）；白名单全链路（user 24 入白 200×3 / 摘白 403 / 无凭证 401，白名单已还原空）。遗留：浏览器侧播放器/阅读器金路径人工验收 + SCF `/kb/stream` 路由排除决策复核随下轮部署。

## 7. 批次 G · 用量看板、清理与一期收口（~1 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| G1 | 用量聚合 | `usage_service.py` + `GET /admin/kb/usage?sourceId=&from=&to=`：台账 `kb_*` 分项 token × 模型单价 + ASR 时长（process_meta）× asrPerHour，预估 vs 实际对照；SettingsTab 用量面板 |
| G2 | 清理任务 | `kb-cleanup`（batch）+ spider + seed `*/30` + F-MON 登记：扫过 24h 恢复窗的软删行 → COS 批删 → 硬删 → storage 清零（已提前接线 2026-09-19：过窗软删物理清除 + 超龄分片会话 abort + 每日孤儿对象扫描；KB 检索投影已随批次 J 摘除——行硬删即检索消失，无 ES 清理步骤；维护类任务不参与 F-MON 健康统计） |
| G3 | 一期收口 | F-MON 五任务判定复核（SKIPPED=正常态）；docker 栈全链路走查（对照需求 §9 验收表逐行）；质量门全绿 |

验收：用量分项与台账一致（抽样对账）；删库级联清理后检索无残留；需求 §9 一期行全部通过。

> **交付记录（2026-09-21，G1/G1b/G2/G3 一期收口）**：G1 完成——`usage_service.py`（台账 `kb_*` 四分项 × 模型聚合 + ASR `process_meta.audio_seconds` × asrPerHour + 清洗 token 字符折算预估对照）+ `GET /admin/kb/usage`（query snake_case：`source_id/date_from/date_to`，北京日历日闭开区间）+ `cost_service.predict_clean_tokens` 公共化复用。G1b 完成——shared 三契约 + `fetchKbUsage`/`useKbUsage` + `UsagePanel.tsx`（源/日期过滤、分项表、ASR 汇总、预估 vs 实际对照）挂 SettingsTab；计价卡补 `vlmPerImage`（可选，视觉分项费用=调用次数×单价）。**走查发现并修复计量上下文缺口**：台账 `detail` 通道从未写入 `sourceId`（`meter_scope` 无 detail 形参、kb 五处调用点零上下文），按库过滤形同虚设——`MeterContext` 增 `detail` 字段贯通 usage_meter 入账，transcribe/extract/vision 调用点带 `{sourceId, mediaId}`，index 嵌入批次同源时记 sourceId（跨源批不归集）；单测钉死 detail 入账 + 容器内结构化调用实测行落 `{"sourceId":1,"mediaId":…}` 且 `?source_id=1` 命中。G2 复核——kb-cleanup */30 接线在位，SKIPPED 良性语义（锁忙/无积压）与失败归因单测 4 条绿；维护类豁免 F-MON（MAINTENANCE_EXEMPT）由域映射测试钉死；软删入口置脏 + 硬删 FK 级联，检索无投影残留。G3 走查——本地栈重建后 usage 端点全量对账（四分项 tokens/调用数与 SQL 逐一相符：clean 41/155,572、extract 300/1,502,624、vision 1219/1,670,176、embed 555/3,304,281；ASR 38 媒体 49,409.3s ¥34.312）、日期区间/未认证 401/vlmPerImage 视觉估算（1219×0.02=24.38）实测通过；质量门全绿（后端 2090 单测 + mypy + ruff；web 372 单测 + typecheck + lint + build）。偏差：query 参数按项目惯例 snake_case（arch 文档 `?sourceId=&from=&to=` 为示意记法）。遗留待办：浏览器播放器/阅读器黄金路径用户人工验收（批次 F 遗留，本地栈已就绪）；KB 上生产前需评估 SCF 900s/响应限制对 `/kb/stream` 长视频代理流的影响（本期本地栈不涉及）。

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

## 9. 批次 J · 检索去投影化：PG 单库混合检索（~2 人日）

> 2026-09-20 追加（ES 投影两次被外部清空事故后评审拍板，arch 12 §1/§7 修订定稿）：撤销「PG 真相源 + ES 可重建投影」双存储，检索收敛为 PG 单库——`halfvec(2048)` HNSW 向量路 + `pg_trgm` 词面路 + 服务层 RRF。动机：投影同步链是独立故障面（本次 9200 端口暴露 + 弱凭据被外部 `delete_by_query` 清空索引；叠加 best-effort 删除、版本对账、mapping 指纹等约 500 行投影管理机械）；语料 ≤1 万行 PG 双索引余量充足；ES 标准分词对中文 BM25 本就无质量红利。ES 容器保留（存量研报索引 + 健康探针），9200 不再对宿主发布。

| # | 任务 | 内容与改法 |
|---|------|-----------|
| J0 | 回滚与备份 | stash 留底 ES 投影实现（含 #188 章节下推 ES 侧），工作树回退；纯 PG 侧成果选择性恢复（章节浏览端点/`20260920e` GIN 迁移/#186 管线健壮化/#187 需求增补） |
| J1 | 迁移与模型 | `docker/database/migrations/20260920f_kb_search_columns.sql`（幂等）：`CREATE EXTENSION vector`/`pg_trgm`；三表 `embedding halfvec(2048) NULL`；point/image `search_text` 生成列（拼接口径 = 嵌入输入单一真相）；三表 HNSW(`halfvec_cosine_ops`) + GIN(`gin_trgm_ops`)；init-scripts 双写；`uv add pgvector`；`models/kb.py` `Halfvec`/`Computed`（sqlite 测试兼容） |
| J2 | 嵌入物化器 | `index_service.py` 重写：脏行扫描 → `embed(检索文本)` → UPDATE `embedding` + 清脏（同事务）；`force_rebuild` 全量置脏重灌（行级覆写，无别名/蓝绿）；维度护栏（实测维度 ≠ 列定义 → SKIPPED 显式引导）；删除指纹/别名/对账/tombstone 全部投影管理 |
| J3 | 检索重写 | `search_service.search`：词面路（ILIKE 候选 + `similarity()` 排序，窗口 50）+ 向量路（`<=>` HNSW，行内 WHERE 过滤与水合口径同源）→ `_rrf_fuse`/kind 分桶截断/水合/响应契约不变；降级语义：embedding 失败仅词面路（`degraded=embedding_unavailable`），无整面失败 |
| J4 | 依赖摘除 | cleanup/transcribe 删 ES 投影调用（保留 `mark_*_children_dirty`）；`spiders/kb_index.py` stats/SKIPPED 契约同步；compose ES 9200 端口不对宿主发布 |
| J5 | 回填与验证 | 从 ES v3 一次性回填 3842 条 embedding（`_source.embedding` → UPDATE + 清脏，零重嵌入）；E2E：「什么是支撑拐点」/「支撑」双路命中、章节过滤、浏览端点回归；质量门全绿 |

验收：同 query 集合召回不低于 ES 版基线；物化任务增量/全量跑通且维度护栏生效；KB 链路代码零 ES 连接；素材删除后检索即时消失；9200 不对宿主发布。

> **交付记录（2026-09-20，批次 J 完结）**：J0–J5 完成——J0 stash 留底（`stash@{0}` "backup: pre-OptionB ES projection"），25 个方向无关文件选择性恢复（#186 管线健壮化/章节浏览端点/`20260920d`/`20260920e`/前端审核台等）；J1 迁移 `20260920f` + init 双写 + `models/kb.py` 三表 `embedding`（`HALFVEC(2048)` 带 sqlite JSON variant；pgvector 0.5.0 类名是 `HALFVEC` 非 `Halfvec`）+ `KB_EMBEDDING_DIMS=2048`；**生成列落地偏差**：`concat_ws`/`array_to_string` 均 STABLE 不可入生成列，改 `CASE/COALESCE/||` 显式拼接（空/NULL 段跳过 + 非空段 `\n` 连接，与 Python join 口径逐点一致，tmp 表实测钉死）；`search_text` 刻意不映射 ORM（sqlite 无该函数，词面路由 raw `literal_column`）。J2 `index_service.py` 696→317 行：`_KindSpec`（model+keep_row+text_of）声明式物化，增量单轮各类 500 / `force_rebuild` 全量置脏 drain；不可见行（rejected/排除/软删/停用源）清 `embedding=NULL`——检索可见性由行状态 + 检索行内过滤双保险，无 tombstone；维度护栏 SKIPPED 引导列迁移。J3 `search_service.py`：词面路 ILIKE（`\`/`%`/`_` 转义防通配注入）+ `similarity()` 排序、向量路 `<=>` HNSW，**各类行分别取序后按分数并成跨类全局序**再进 RRF（保持 ES 版「两路各一个全局序」的融合语义）；kind/point_type/章节过滤经 `_leg_active` + `_Scope` 同构透传两路，章节 = JSONB containment 粗筛（WHERE）+ 前缀精筛（水合）；降级收敛为仅 `embedding_unavailable`（PG 故障随请求 500，无 `es_unavailable` 静默空）；`KB_INDEX_ALIAS`/`KB_INDEX_PRUNE_DAYS` 孤儿常量删除。J4 cleanup/transcribe 投影调用摘除（向量随行生存：软删下轮物化清、硬删 FK 级联消失）；spider stats 契约（Embedded/Cleared/dimensionMismatch/forceRebuild）；compose 两文件 ES 端口发布移除（网内可达，研报索引与健康探针不受影响）。J5 回填脚本 `scripts/backfill_kb_embedding_from_es.py`（scroll v3 → `$1::halfvec` 文本参数 + 清脏，asyncpg 免 codec 注册），本地实跑 point 721 / seg 1994 / img 1127 全量入列零重嵌入、脏标全清。质量门：后端 2039 单测 / mypy / ruff 全绿。E2E：`支撑` 双路命中（degraded=None，点 8 + 段 10 + 图 1，案例帧缩略图与 seekMs 齐备）、章节树/浏览清单/章节过滤检索/kind=image 文字搜图全通、`kb-index` 增量空转 SKIPPED 正常（维度探测真实调通智谱）。

### 批次 K · 全系统去 ES（2026-09-21 追加，~1 人日）

> 2026-09-21 拍板（批次 J 后余量评审）：剩余 ES 使用面仅三处——财报 PDF 全文投影（`kb-documents`，研报从未入 ES）、Agent 工具 `search_vector_kb`（唯一查询消费方，研报搜索一直在走 `news_document` 兜底）、系统状态 ES 探针；加上 `news_document.elasticsearch_doc_id` 死列（全部写 NULL）。**研报+财报全文都进 PG**（`file_metadata.content` + GIN trgm），存量 MinIO 重抽回填（不依赖 ES，退役顺序解耦），ES 容器/依赖/探针全退役。prod 侧唯一前置：`backfill_kb_embedding_from_es.py`（批次 J 的 KB embedding 回填）须在 ES 下线前跑完，否则走 `kb-index` force_rebuild 全量重嵌。

| # | 任务 | 内容与改法 |
|---|------|-----------|
| K1 | 迁移 | `20260921_file_content_pg.sql`（幂等）：`file_metadata.content TEXT` + `GIN(content gin_trgm_ops)`；`news_document` 删 `elasticsearch_doc_id` 死列；init-scripts 双写 |
| K2 | 全文入库 | 新 `app/services/common/pdf_text.py`（`extract_pdf_text`，pypdf 尽力而为）；删 `common/knowledge_base_service.py`（ES 索引服务）；两个 store（financial/research）入库时抽取全文写 `content`（失败不阻塞，保留旧值）；summarizer 懒导入改 pdf_text |
| K3 | 检索工具 | `search_vector_kb` 改纯 PG：`file_metadata` 标题/全文 ILIKE + `report_date DESC`，空结果兜底 `search_news`（工具名与三处引用不动）；repository 列表查询 `defer(content)` 防 MB 级全文拖带 |
| K4 | 退役清扫 | 系统状态探针删 ES 项；`config.elasticsearch_url` + `elasticsearch[async]` 依赖 + 5 个传递依赖移除；两个 compose 删 elasticsearch 服务（prod `ELASTIC_PASSWORD` 必填项随之消失）；`.env.example` 清理；死列清扫（schema/admin news/2 spider） |
| K5 | 回填与文档 | `scripts/backfill_file_content.py`（MinIO 下载 → pypdf → PG，逐条 best-effort，幂等可重跑）；arch 00/01/03/04/06/12、README、CLAUDE.md、需求 04 ES 表述更新 |

验收：`search_vector_kb` 全文命中研报/财报特征词（首次可搜研报全文）；系统状态无 ES 项；`docker compose ps` 无 elasticsearch；列表接口响应体不因 content 变大；单测/mypy/ruff 全绿。

> **交付记录（2026-09-21，批次 K 完结）**：K1–K5 完成——K1 迁移 `20260921_file_content_pg.sql` + init 双写。K2 `pdf_text.py` 抽取函数迁自原 `_extract_pdf_text`；`knowledge_base_service.py` 删除（140 行 ES 索引服务）；financial store ES index 块 → `content` 写入（try/except best-effort，抽取失败保留旧值不置 NULL，可被回填脚本重试），research store MinIO 上传后补全文写入；两个 summarizer `_extract_text` 懒导入改 pdf_text。K3 `search_vector_kb` 改 `file_type IN ('research_report','financial_report')` + 标题/全文 ILIKE + `report_date DESC`，返回契约 `{title, content[:300], publish_date}` 不变，空结果兜底 `search_news`（此前研报搜索一直在走此兜底——ES 内从未有研报全文）；repository 两处 `defer(FileMetadata.content)`。K4 探针删 ES 项（模块 docstring/前端注释同步）；pyproject 删 `elasticsearch[async]`（uv lock 连带清 yarl 等 5 个传递依赖）；compose 两文件删 elasticsearch 服务块；`.env.example` 删 `ELASTICSEARCH_URL`/`ELASTICSEARCH_PORT`/NO_PROXY 项并重排小节；死列清扫（model/schema/admin news/eastmoney_flash_news/cninfo_disclosure）。K5 回填脚本 ES-free（MinIO + PG 直连），`backfill_kb_embedding_from_es.py` 保留（prod KB embedding 回填仍需）。质量门：后端 2043 单测（新增 store content 写入 3 例 + search_vector_kb PG 双路 2 例，ES 探针/死列断言更新）/ mypy / ruff 全绿。

## 10. 批次 H · 二期 Agent 消费（F-KB-06/07，~3 人日）

| # | 任务 | 内容与改法 |
|---|------|-----------|
| H1 | 检索工具 | `search_knowledge_base(query, source?, chapter?, point_type?)` 注册进 `build_assistant_tools()`，按会话权限注入（admin / 白名单，普通用户不注册）；压缩卡片集受 top_k 约束；降级返回明确错误文本；分析类技能（复盘/异动/涨停）SKILL.md allowed-tools 增补 + 提示词声明引用规范 |
| H2 | 优化建议单 | `kb_optimization_suggestion` 表（迁移 + 双写）；后台选「目标技能 × 知识源」手动触发 → 优化 Agent 读技能定义 + 检索知识点 → 修改点列表（原文/建议文/diff + 理由 + 引用定位）；同技能存在未处理单时禁止新发 |
| H3 | 审核与应用 | 建议 API + 审核队列 UI（通过/修订后应用/驳回）；custom 技能 version+1 直写生效；builtin 导出完整文件文本 + 变更说明交开发落库（运行时不改代码库文件）；建议单全量留档 |

验收：普通用户会话无此工具（单测钉死）；未经审核的修改不生效；引用带集数/时间码可溯源。

## 11. 部署前置与运维项（随对应批次落地）

- **依赖**：批次 C 文本层已用 `pypdf`（pyproject 已含）；批次 F 新增 `uv add pypdfium2 Pillow`（书页渲染 + 水印合成）+ **web 镜像补 CJK TTF 字体层**（水印中文渲染）；**collector 镜像补 ffmpeg**（apt 层，批次 B 转写切分依赖）——Dockerfile 变更随批次 B 提交；批次 J 新增 `uv add pgvector`（SQLAlchemy `Halfvec` 类型，纯轮子）。
- **SCF 路由决策（批次 F 开工前定）**：`/kb/stream` 视频代理仅由轻量服务器域名提供，SCF Web 函数路由排除（2048MB 内存/流式响应红线）；KB 为内部功能，不阻塞开发、阻塞验收。
- **批次 I 零新增依赖**：ffmpeg 复用 collector 镜像既有层（批次 B 已补）；aHash 纯 Python 实现，不引 Pillow；抽帧走 subprocess。
- **compose 零新增服务**（零 sidecar）；~~ES 容器保留但 KB 不再连接~~ → **ES 容器已全栈退役（2026-09-21 批次 K）**：研报/财报全文入 `file_metadata.content`（pypdf + GIN trgm），`search_vector_kb` 改 PG 词面检索，健康探针摘 ES 项，compose 删 elasticsearch 服务与 9200。
- **admin 前置配置**（联调前）：`llm_config` 登记 embedding（智谱 embedding-3 2048d）与 vision 条目并绑定四槽位；ASR 渠道复用 F-SOC `asr_channel_config`；asr-1.0 控制台试跑 1 集核价并回填 `unit_prices`（单价未公开刊例，预估失真告警项）。
- ~~`elasticsearch[async]>=8.13,<9` 客户端锁定维持~~ → 依赖已随批次 K 移除（pyproject + uv.lock）。

## 12. 风险速查（详见 arch 12 §16）

asr-1.0 单价未刊例（核价前置 + 渠道可插拔 Paraformer 兜底）｜扫描版混入（解析显式拒收）｜模型角色误配置（保存/启动双校验 + FAILED 归因）｜抽取幻觉（三层防线 + 人工审核）｜检索底座 PG 单库（trgm 无词法权重语义，长自然语言查询靠向量路承载，RRF 双路不落空）｜防盗不承诺防录屏（水印溯源边界）｜关键帧漏采与视觉成本（三路信号互补 + 单集配额 + describe 退避 + 台账对账）。
