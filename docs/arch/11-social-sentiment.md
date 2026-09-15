# 社媒大 V 情绪追踪架构设计

> 闭环：管理员登记抖音追踪账号（平台级清单）→ 自研抖音适配层轮询采集新视频 → 云端 ASR 转写（临时文稿）→ LLM 结构化多空判断 → `social_*` 落库 → 资讯中心第四 Tab「大 V 情绪」（情绪流 / 账号维度）→ 后台「社媒追踪」管理 + F-MON 健康监测全程覆盖。
> 需求：[docs/requirement/06-social-sentiment-requirement.md](../requirement/06-social-sentiment-requirement.md)（F-SOC-01/03/04/05 一期）· 原型：[docs/prototypes/social-sentiment.html](../prototypes/social-sentiment.html)（资讯中心第四视图口径）

## 1. 设计原则

1. **LLM 只见增量**：视频以 `(platform, video_id)` 幂等去重（落库冲突即跳过），判断结果与 post 一对一缓存（已判永不重判）——采集可反复重跑，判断成本恒等于新增内容量。
2. **转写是输入不是资产**：文稿只作判断输入的临时落库缓存，判断成功即置 NULL，任何 API 永不透出；平台持久展示物仅「分析结论 + 摘要 + 封面 + 原文外链」（合规边界，钉死在 schema 与测试两层）。
3. **采集与判断分离为两类 collector 任务**：采集失败是渠道问题（FAILED，重试/fallback），判断失败是输入问题（保留待判、退避重试）；账号长期无新视频是无害 SKIPPED——三种终态语义分明，F-MON 据此免误报。
4. **视图是 `social_*` 表的只读派生**：平台级单一清单，无用户级状态；删账号即停采集，历史保留、视图按 `is_active` 隐藏。
5. **零框架改动**：TaskSpec 注册、PostgresCollector 落库、`run_structured` 结构化判断、渠道注册表、F-MON 判定、CamelModel wire 全部复用既有范式；本需求只新增 spec/spider/service/模型/页面。
6. **立场配色走 scheme-aware**：看多红/看空绿经 `formatters` helpers + `useColorScheme()`，与全站涨跌配色同源，不硬编码。

## 2. 数据模型

迁移 `docker/database/migrations/20260915_social_sentiment.sql`（幂等）+ `init-scripts/01-schema.sql` 双写（[03-data-storage](./03-data-storage.md) 规范）；SQLAlchemy 模型落 `backend/app/models/social_*.py`（单数表名 + `social_` 前缀，`Mapped` 2.0 风格，审计字段用 `app.core.clock.utc_now`）。

| 表 | 键与约束 | 说明 |
|----|----------|------|
| `social_account` | uq `(platform, sec_uid)`；idx `(is_active)` | `platform CHECK ('douyin')`（预留扩展）、`sec_uid`（平台内唯一标识）、`alias`、`category VARCHAR(32)`（常量注册：`macro_policy`/`finance_kol`/`industry`，不入 CHECK 以便扩展）、`remark`；`poll_interval_minutes INT DEFAULT 60`；`is_active BOOLEAN`；`last_collected_at`/`last_post_at`；`last_error`/`last_error_at`（渠道侧账号失效诊断提示，不阻断采集） |
| `social_post` | uq `(platform, video_id)`；idx `(published_at DESC)`、`(account_id, published_at DESC)`、`(judged_at)` | `account_id FK CASCADE`、`video_id`、`title`/`caption`/`topic_tags JSONB`/`cover_url`/`duration_seconds`、`published_at`（发布时刻，aware UTC）；互动 `digg_count`/`comment_count`/`share_count`；`transcript_status CHECK ('ok','missing')`（采集时刻即定，音频获取失败降级 `missing`）；`transcript_text TEXT NULL`——**临时文稿缓存，判后即清**；`transcript_meta JSONB`（ASR 用量对账：音频时长/字符数/渠道标识）；`judged_at TIMESTAMPTZ NULL`（NULL=待判，判断幂等键） |
| `social_sentiment` | uq `(post_id)`（1:1，判断按内容缓存）；idx `(created_at DESC)`、`(stance, created_at)` | `post_id FK CASCADE`；`is_relevant BOOLEAN`（无关内容不入视图）；`stance CHECK ('bullish','bearish','neutral')`；`confidence REAL CHECK (0~1)`；`core_arguments JSONB`（一句话论点数组）；`targets JSONB`（`[{type: index/sector/stock/commodity, name, code?}]`）；`summary`；`model_name`（判断对账/审计） |

seed：`init-scripts/03-seed.sql` 加 `collector_task` 两行（见 §5）；抖音渠道行由 `collector/runtime/channels.py` 的 `DEFAULT_CHANNELS` 幂等 seed。

## 3. 采集与转写（F-SOC-03）

### 3.1 内容获取渠道（自研抖音适配层）

抖音 web 端无公开内容 API，采集走**自研适配层**（`backend/app/adapters/douyin/`，collector 内置，零新增部署容器）。只实现本需求的窄能力面——指定账号的作品列表 + 作者资料，不做全站搜索/评论/下载器。技术路线（已定稿）：

- **传输层**：curl_cffi（Chrome TLS 指纹模拟）——抖音按 TLS 指纹识别非浏览器流量，标准 httpx 指纹会被拦截；curl_cffi 是仓库已验证的对抗手段（东财研报 PDF 下载先例）。
- **签名层**：a_bogus 请求签名**纯 Python 移植**，隔离在单点模块 `signing.py`（算法参考开源实现移植，模块头注明出处），输入=查询参数+UA+时间戳、输出=签名查询串；抖音升级算法时只更新该模块，任务定义与 spec 零改动。
- **Cookie 层**：douyin web 需要浏览器指纹 Cookie（ttwid / UIFID_TEMP 等），两级供给：① 自动自举——curl_cffi 访问抖音首页捕获下发 Cookie；② 手动兜底——管理端渠道配置粘贴浏览器 Cookie 串（Fernet 加密落库、masked 展示）。轻量轮换：2~3 个 Cookie jar 轮替 + 失效检测重建；**不建完整身份池**（指纹/代理终身绑定、无头浏览器自动铸造属重火力方案，本系统每账号 1 次/小时的量级用不上）。
- **渠道接入**：`DEFAULT_CHANNELS` 新增 `source='douyin'` 行（`base_url='https://www.douyin.com'`，管理端可改；`supported_data_types=['social_video']`）。
- **使用的端点**（aweme web 接口）：
  | 端点 | 用途 |
  |------|------|
  | `GET /aweme/v1/web/user/profile/other/` | 作者资料（`sec_user_id`）：登记校验、别名/头像核对、账号失效判定 |
  | `GET /aweme/v1/web/user/post/` | 账号作品列表：`sec_user_id` + `max_cursor` 游标，`count` ≤20；小时级轮询下单页覆盖增量 |

  主页分享短链（v.douyin.com）由适配层自行展开（跟随 302 提取 sec_uid）。
- **解析容错**：原始 `aweme_list` → 归一化字段搬运（`aweme_id`→video_id、`desc`→title/caption、`create_time`→published_at、`video.duration`→duration_seconds、`video.cover`→cover_url、`statistics.{digg,comment,share}_count`→互动三列、`text_extra` 话题→topic_tags、`author.sec_uid`→归属校验）。aweme 结构随版本漂移：单字段缺失置 null 容错，顶层结构巨变显式报错（结构漂移错误码，见下）。
- **故障语义显式归因**（三类不混淆，F-MON 据此告警与豁免）：
  | 归因 | 判定 | 处置 |
  |------|------|------|
  | 签名失效 | 状态/响应码呈一致的签名拒绝特征 | 不重试，F-MON critical「签名算法需更新」，更新 `signing.py` 恢复 |
  | 命中风控 | 验证码挑战/异常空数据 | Cookie 冷却退避（分钟级指数）、换 jar 重试，连续命中升级告警 |
  | 账号失效 | profile 404 / 私密 / 不存在 | 记 `social_account.last_error`，不重试不停用（停用是管理员决策） |

  网络/服务级失败 = 采集 FAILED（无 fallback 渠道，collectors 单 source），退避重试 + F-MON 告警 + 视图横幅，不波及资讯中心其余视图。生产服务器须能直连抖音（国内云满足）。

### 3.2 采集任务 `social-video`（external）

`collector/spiders/social_video.py`：`DouyinVideoCollector(PostgresCollector)`，声明 `table='social_post'`、`conflict_key=(platform, video_id)`——同视频重复采集被 ON CONFLICT 吸收，天然幂等。

```
collector_task: social_video_poll（source=douyin，每小时）
  └─ 遍历启用账号（last_collected_at 早于各自 poll_interval_minutes）
       ├─ 适配层拉账号作品列表（sec_user_id + max_cursor；单页起，has_more 且本地缺视频时续拉，上限 3 页防长尾）
       ├─ 新视频（video_id 冲突即跳过）→ 无水印播放地址拉流至临时文件 → ffmpeg 抽音轨 → 云端 ASR（热词注入）
       │     └─ 音频获取/转写失败 → transcript_status='missing'，仅文案继续（不阻塞）
       └─ social_post 落库（judged_at=NULL 待判）
```

- 账号级轮询间隔存 `social_account.poll_interval_minutes`（`collector_task` 表无参数列，账号参数不进 spec）；任务小时级心跳 + 账号级间隔过滤，默认 1 小时/账号。
- 账号失效（profile 404/私密，§3.1 归因表第三类）：记 `last_error`/`last_error_at` 供管理端提示，连续失败由 F-MON 判定，不自动停用（停用是管理员决策）。

### 3.3 ASR 转写服务

云端 ASR API 渠道化配置在本需求独立落地（04 知识库后置排期，届时直接复用同一设施）：

- 单行配置表 `asr_channel_config`：`provider`/`base_url`/`model`/`api_key_encrypted`（Fernet，`app/utils/crypto.py` 同一路径）/`api_key_masked` 冗余脱敏串/`hotwords JSONB`（财经热词表，与 04 共用一份语义）/`enabled`。
- 转写由采集任务内联执行（媒体到手即转，音轨由 ffmpeg 从无水印播放地址本地提取，音频/视频临时文件即用即删——与「不留存原片」合规一致）；用量记入 `social_post.transcript_meta` 逐条对账；单条音频时长上限截断（超长视频不整条转写）。

## 4. 情绪判断（F-SOC-04）

### 4.1 任务 `social-sentiment`（internal AI）

`collector/spiders/social_sentiment.py`：仿 `news_ai_score` 触发式 spider——`collect()` 返回空，`run()` 直调服务层；无待判内容返回 SKIPPED（正常态，不告警）。

```
collector_task: social_sentiment_judge（source=internal，每 10 分钟）
  └─ sentiment_service.judge_pending(session)
       ├─ redis_lock 单实例（阻塞即让位，下轮再扫）
       ├─ 扫描 judged_at IS NULL 增量（单轮上限 M 条）
       ├─ run_structured(SocialJudgmentResult)  # 文稿（或降级仅文案 + missing 标注）注入 prompt
       ├─ 幻觉标的轻校验：targets 的 stock 代码不在股票基本表 → 剔除该条 target
       ├─ social_sentiment 落库 → post.judged_at=now + transcript_text=NULL（判后清稿）
       └─ 顺手清理：滞留 >7 天仍未判的临时文稿置 NULL（防文稿长期滞留，不新增定时任务）
```

- 判断失败（LLM/网络异常）不阻塞采集：内容保留待判，任务抛错走 celery 退避重试（对齐 `ReviewInputDataNotReadyError` 输入未就绪既有模式）；积压超时效窗口的批量补判 = 采集管理既有「手动补跑」该 internal 任务，不新增端点。
- 同一视频不重复消耗 LLM：判断前按 `post_id` 查 `social_sentiment` 命中即跳过（缓存优先，与 `judged_at` 双保险）。

### 4.2 判断契约（结构化输出，全字段必填）

- skill 资产：`skills/social-sentiment/{SKILL.md, prompt.yaml}`，`app/skills/registry.py` 登记 `SkillDescriptor(kind="prompt_only", skill_md=True, scenario="news", task_spec_names=("social-sentiment",))`。
- Schema `app/schemas/social.py`：`SocialJudgmentResult { relevance: bool; stance; confidence; core_arguments: list[str]; targets: list[SocialTarget]; summary: str }`——**全字段 required、禁带默认值**（项目铁律，news-score 空结果事故教训，钉死单测）。
- 调用走 `run_structured`（Celery 路径不传 user_id，system 维度）；LLM 幻觉项按回传 post_id 过滤（news-score 同款防线）。

## 5. 任务注册与调度

| 项 | 值 |
|----|----|
| TaskSpec | `collector/runtime/specs/social.py` 新增两条并在 `ALL_SPECS` 登记：`social-video`（data_type `social_video`，collectors `{'douyin': …DouyinVideoCollector}`）、`social-sentiment`（data_type `ai_social_sentiment`，collectors `{'internal': …SocialSentimentCollector}`） |
| seed | `03-seed.sql`：`('social_video_poll','social-video','douyin','0 * * * *',true)`、`('social_sentiment_judge','social-sentiment','internal','*/10 * * * *',true)`（北京时间） |
| 调度 | Celery beat `CollectorDatabaseScheduler` 动态加载 `collector_task`，零框架改动；默认 batch 队列（单轮增量上限防超 600s 软限，必要时 `_QUEUE_OVERRIDES` 调 heavy） |
| 健康监测 | F-MON 注册表登记 `(social-video, douyin)` 与 `(social-sentiment, internal)` 两条；判定语义：无新视频/无待判 = SKIPPED 正常，渠道不可用/判断连续失败 = FAILED 告警 |

## 6. API 面（wire camelCase；query snake_case）

### 6.1 用户侧（`api/v1/social.py`，登录态，薄路由 + `Query` 分页约束）

| 端点 | 说明 |
|------|------|
| `GET /social/sentiment-feed?category=&stance=&hours=&strongOnly=&page=&page_size=` | 情绪流分页：post + account + sentiment 联查，仅 `is_relevant` 且已判且账号 `is_active`，按 `published_at DESC`；`strongOnly=true` 等价 `confidence ≥ 0.8`；跨日分组由前端按 `publishedAt` 派生 |
| `GET /social/accounts` | 账号卡：别名/分类/最近更新时间（`lastPostAt`）/最新立场+置信度/近 7 日多空计数（服务层聚合） |
| `GET /social/accounts/{id}/timeline?page=` | 单账号已判内容时间线（立场轨迹由前端按序派生连续同向/转向） |

响应 schema `app/schemas/social.py`（CamelModel）：`SocialFeedItem`/`SocialAccountCard`/`SocialTimelineItem`；`transcript_text` 不在任何响应模型中（类型层即不可泄漏）。P2 的 `GET /social/temperature` 后置留位。

### 6.2 管理侧（`api/v1/admin/social.py`，admin 依赖 + `record_audit`）

| 端点 | 说明 |
|------|------|
| `GET /admin/social/accounts?page=&active=` | 清单分页（含 `lastError` 诊断列） |
| `POST /admin/social/accounts` | 登记：`{platform, secUidOrUrl, alias, category, pollIntervalMinutes?, remark?}`；服务层解析 sec_uid（标准主页链接正则提取，短链由适配层展开）；同 `(platform, sec_uid)` 重复登记 409 |
| `PATCH /admin/social/accounts/{id}` | 别名/分类/间隔/启停/备注 |
| `DELETE /admin/social/accounts/{id}` | 停采集、历史保留、视图隐藏 |
| `GET /admin/social/status` | 只读聚合：douyin 适配层健康（Cookie 池可用 jar 数与最近自举时间；签名拒绝连续出现透出「签名算法需更新」警示；今日采集量/失败数源自 collector_log）+ ASR（今日转写数/降级数，源自 transcript_meta） |
| `GET/PUT /admin/social/asr-config` | masked 视图；PUT 时 `apiKey` 可选（留空不换），审计 `social.asr_config.update` |

错误码：`SOCIAL_ACCOUNT_DUPLICATE`（409）/ `SOCIAL_ACCOUNT_INVALID`（400，sec_uid 无法解析）。审计动作：`social.account.create/update/delete`。手动补跑复用既有采集管理「按任务手动补跑」通道。

## 7. 前端

### 7.1 资讯中心第四 Tab（F-SOC-05）

```
web/src/pages/News/components/Sentiment/
├── SentimentView.tsx      # Tab 容器：二级导航（情绪流/账号维度）+ 渠道中断横幅 + P2 情绪温度占位
├── SentimentStream.tsx    # 筛选 chips（分类/立场/时间/仅看强信号 Switch）+ 复用 FeedList/FeedToolbar/FeedPagination
├── SentimentCard.tsx      # 9:16 封面缩略图（时长角标）+ 立场徽标 + 摘要 + 论点列表 + 标的 chips + 互动数 + 原文外链
├── AccountDimension.tsx   # 账号卡 grid → 单账号时间线（立场轨迹连续同向/转向徽标）
└── StanceBadge.tsx        # scheme-aware 立场徽标（changeHex + useColorScheme 订阅）
```

- `pages/News/index.tsx` Tabs items 追加第四项 `{key:'sentiment', label:'大 V 情绪'}`；跨日分隔条复用 `News/logic.ts` 的 `groupByDay`；发布时间走 `formatRelativeTime` + Tooltip 精确时刻（既有范式）。
- 立场徽标/温度色一律 `formatters` scheme-aware helpers（bullish→红系、bearish→绿系，跟随配色方案）；标的 chips 按类型跳板块详情页/个股详情页；高置信度 + 高互动卡片加重/置顶标记。
- 渠道中断横幅：SentimentView 读 `useNewsChannels()`，douyin 卡 `delayed`/中断时显示「部分渠道采集中断」，不影响其余 Tab；抖音渠道卡经渠道注册表落地后 ChannelMonitorBar 自动出卡（注册表驱动，无前端枚举）。
- 契约与数据层：`shared/types/social.ts`（wire camelCase）+ `shared/api/endpoints.ts` 注册 + `web/src/api/social.ts`/`adminSocial.ts` + `hooks/queryKeys.ts` 新增 `social` namespace；TanStack Query 惯例（分页 feed、mutation 失效）。

### 7.2 后台「社媒追踪」（F-SOC-01）

`pages/Admin/SocialTracking/`（页面 + `SocialAccountModal` + `AsrConfigModal` + `CookieImportModal`）：账号表（启停 `Switch` + armed 两步删除，复刻 CollectorChannelConfig 表格 Switch 与画线页 armed 范式）、渠道状态双卡（抖音适配层 / ASR 转写服务，读 `/admin/social/status`，只读，启停走任务管理；抖音卡透出 Cookie 池状态与最近自举时间，连续失效时提示「前往渠道配置粘贴浏览器 Cookie 兜底」并提供粘贴入口）、ASR 配置弹层（密钥 write-only + masked 展示）。注册三处：`router.tsx`、`Sidebar.tsx ADMIN_MENU_ITEMS`、`Admin.tsx ADMIN_LINKS`。

## 8. 后端模块布局

```
backend/app/adapters/douyin/        # 自研抖音适配层（窄能力面：作品列表 + 作者资料）
├── transport.py                    # curl_cffi Chrome TLS 指纹会话、Cookie jar 轮换
├── signing.py                      # a_bogus 签名单点模块（开源实现移植，算法升级只改此处）
├── cookies.py                      # Cookie 自举/手动兜底（Fernet 加密）、失效检测
└── api.py                          # aweme web 端点封装 + 归一化解析 + 故障归因

backend/app/services/social/
├── account_service.py     # sec_uid 解析、CRUD、重复校验（管理端）
├── collection_service.py  # 采集落地：新视频识别、媒体下载、降级标注、post upsert（spider 调用）
├── asr_service.py         # ASR 渠道调用：加密凭据、热词注入、时长截断、用量记账
└── sentiment_service.py   # 判断编排：锁 + 增量扫描 + run_structured + 幻觉过滤 + 判后清稿

backend/app/repositories/social/
├── account_repository.py
└── post_repository.py     # post/sentiment 联查聚合（feed/timeline/账号卡/待判扫描）

backend/app/constants/social.py   # platform/category/stance/target_type 枚举、Redis 锁键
backend/app/schemas/social.py     # LLM 判断契约（全 required）+ CamelModel 响应
backend/app/api/v1/social.py · api/v1/admin/social.py
```

依赖方向遵守既有分层：adapters 是纯下游叶子（只被 collector spider 与 app services 导入，自身不反向导入 app 层，不构成 services↔collector 解环）；services 不顶层导入 `app.agent.tools/skills/runtime`（`run_structured` 经函数内延迟导入）；浏览器 Cookie 兜底与 ASR 凭据均走加密配置行（Fernet），不入 `config.py`/env。

适配层无独立部署：`curl_cffi` 依赖进 `backend/pyproject.toml`（镜像随之构建）；`signing.py` 随版本发布维护（抖音升级签名算法时更新移植实现，黄金样本单测回归）；生产服务器须能直连 douyin.com（国内云满足），代理配置复用既有 `proxy_config` 渠道绑定能力。

## 9. 验证

- 单测（`backend/tests/unit/`）：判断 Schema「无默认值」钉死测试（防铁律回归）；sec_uid 解析（直接/标准链接/短链/非法）；a_bogus 签名黄金样本（固定输入断言输出，防移植实现回归）；Cookie 自举解析与手动导入加密落库；aweme 解析容错（单字段缺失置 null、顶层结构巨变显式报错）；采集幂等（conflict 跳过、增量上限）；降级链路（音频失败 → missing → 仅文案判断）；判后清稿与滞留清理；幻觉标的过滤；重复登记 409；feed 过滤器与分页；账号卡聚合。
- 前端测试：SentimentStream 筛选/跨日分组/降级卡展示；StanceBadge 随配色方案切换；后台启停 Switch 与 armed 删除；wire 类型同构。
- docker 栈走查（对照需求 §9 验收）：Cookie 自举成功（失败时管理端粘贴兜底）→ 登记账号 → 1 小时内采集 → 转写 → bearish 徽标 + 论点 + 标的 chips 出现在情绪流 → 生活视频判 irrelevant 不入流 → 音频失败降级卡 → 渠道停摆横幅 + F-MON 告警（SKIPPED 不误报）→ 同视频重跑不重复消耗 → 删账号视图隐藏。
- 质量门：backend `uv run mypy app/`、`ruff check .`、`pytest -m unit`；web typecheck / lint / test / build。

## 10. 风险与边界

1. **抖音风控与签名维护（自研路线主要风险）**：平台随时可能升级风控手段（TLS 指纹库、签名算法、Cookie 校验）——缓解：三类故障显式归因（签名失效/命中风控/账号失效）让 F-MON 一眼定位；a_bogus 单点模块 + 黄金样本单测让跟版成本可控；curl_cffi 指纹模拟是仓库已验证手段。Cookie 会随时间失效，双轨供给（自举 + 手动兜底）+ 2~3 jar 轮换在本系统量级（每账号 1 次/小时）够用；若未来量级上涨再评估引入开源身份池方案。
2. **ASR 成本与长音频**：云端按时长计费，单条时长上限截断 + 仅增量转写 + `transcript_meta` 逐条对账；降级路径（missing）反而省成本但损失判断输入，横幅与角标让降级可见。
3. **LLM 幻觉标的**：个股代码做存在性轻校验（不在库即剔除）；板块/指数/商品名称不做强校验（一期容忍，跳转失效由前端兜底）。
4. **文稿与媒体合规**：临时文稿判后即清 + 滞留 7 天兜底 + API 类型层不透出；媒体不落盘、临时文件即用即删；平台条款与内容版权归原平台与作者，视图标注「AI 生成，非投资建议」。
5. **单渠道无 fallback**：douyin 渠道故障即中断（这与多渠道资讯域不同），依靠 F-MON 快速告警 + 视图明示，而非静默缺数；采集仅走只读公开端点 + 平台级登记清单，能力面收敛。

## 11. 后续文档索引

- [02-data-collection.md](./02-data-collection.md) — collector 任务体系、渠道注册表与 F-MON 健康监测
- [04-ai-agent.md](./04-ai-agent.md) — `run_structured` 结构化输出与 skill 资产
- [03-data-storage.md](./03-data-storage.md) — 表命名约定与幂等迁移双写规范
- [05-web-frontend.md](./05-web-frontend.md) — 资讯中心页面结构与后台管理页组织
