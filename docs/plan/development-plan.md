# 功能开发计划

> 需求基准：[01-requirement.md](../requirement/01-requirement.md)；架构与实现方案见 [docs/arch/](../arch/)。
> 本文档只维护迭代级计划与完成状态；实现细节、调研与实施过程沉淀在 arch 文档与代码提交历史中，不在此回填。

## 1. 当前基线

V1.3 已于 2026-09-12 随异动分析迭代全量发布。截至 2026-09-26，需求 01/02/03/05/06 与知识库 04 全部交付完毕（迭代历史与 PR 编号见 git 历史，交付记录见 docs/arch/ 各文档），已交付能力域：

- **数据与采集**：电报准实时、全球指标行情、投资日历、板块行情、采集健康监测（F-MON）、采集管理台、交易日历（DB 权威日历 + 调度预检 + 后台月历管理，2026-09-26 PR #79）
- **AI 分析**：大盘/个股复盘（六分区契约 v3.0.0 + 技术面/情绪面预计算 + 财务自动补采）、涨停归因、AI 选股（问财）、自选 AI 每日分析、产业链图谱与提醒
- **异动检测**：板块/个股检测与 AI 归因，融入趋势理论（板块四维 / 个股三类拐点 / 周线 M60 门控 + 知识库引用契约）；合并页双 Tab
- **K 线**：画线一期（五类型 + Agent 读画线）、AI 智能画线（ask_user 问题卡 + 人工编辑采纳）
- **资讯与社媒**：资讯中心（渠道监控 / AI 分级 / 事件故事线 / 订阅 / 热点主题榜）、大 V 情绪追踪（抖音自研适配 + ASR 转写）
- **知识库 F-KB**：一期全链路（素材转写 / 关键帧 / 抽取审核 / PG 单库混合检索 / 播放阅读防盗 / 用量看板）+ 全系统去 ES；二期 Agent 检索工具注入与媒体引用；技能优化建议链路已下线，能力提升方向并入模拟盘学习闭环（paper-trading 批次 9）
- **模拟交易 F-SIM**：平台层已交付（掘金仿真柜台 REST sidecar、多租户账户管理、人工交易面板——下单/撤单/持仓/委托成交/净值/盘后同步、agent 专属账户指定与解绑，2026-09-24 PR #65 + 2026-09-26 agent 解绑）；交易 Agent 闭环批次 5-7 已交付（独立会话/专属工具/配置面，盘后日周月分层复盘，每日选股与交易计划 + agent 自选分组 + 方法论基座 KB 直读双层注入，2026-09-26 PR #80-#83）；方案与批次拆分见 [paper-trading-plan.md](paper-trading-plan.md)（D1-D20 已拍板）；多 Agent 基座与贾维斯总览立项见 [agent-hub-plan.md](agent-hub-plan.md)（D21-D26 已拍板）
- **平台**：账号准入与 AI 用量治理（审批 / BYOK / 配额计量）、技能广场、MCP 服务管理、个人设置

## 2. 待开发（单人节奏约 1~2 周/迭代）

| 迭代 | 主题 | 内容概要 | 状态 | 依赖 / 风险 |
|------|------|----------|------|--------------|
| 迭代 19 | Agent Hub · 多 Agent 基座与贾维斯总览 | [agent-hub-plan.md](agent-hub-plan.md)（D21-D26）：`trading_agent` 注册表取代单例 config、`is_agent`→`agent_key`、三表+自选分组加 agent 维度，服务/工具/运行时/spider/API 全链路参数化（本批仅 short-line 激活，长线/M60 planned）；`/trading-agent` 总览页（Canvas 雷达 HUD + 活动时间轴）+ 详情页 agentKey 参数化 + 介绍卡 | 已交付（2026-09-26 PR #85） | 六表迁移较大；先于批次 8 落地，批次 8/9 直接建在多 Agent 基座上 |
| 迭代 19.5 | Agent 人设与专属 Skill | [agent-hub-plan.md](agent-hub-plan.md)（D27）：三个会话人设 YAML（prompt_id 分流）+ `skills/trading-<agent_key>/` 作业程序包（BUILTIN_SKILLS 新增 trading 场景，计划生成按 agent_key 装载，广场不展示）+ 复盘 user_prompt 注入注册行人设段 | 已交付（2026-09-26） | 长线/M60 数据源（财务/估值/M60 分钟线）接入后再激活；激活=置 status + 指定账户 |
| 迭代 19.7 | Agent Hub 验收修复与扩展性定版 | [agent-hub-plan.md](agent-hub-plan.md)（D28）：注册表加 plan/review_cadence 频率列 + 任意状态可编辑（status 白名单 active/disabled）+ 人设运行时注入（fingerprint 失效缓存，编辑即时生效）+ 雷达仅 active 像素椭圆（修越界裁剪/双层错位）+ 总览「Agent 管理列表」+ 时间轴可点 + plans 次日语义包装 + 自选行复用自选样式 + `trading-default` 共享技能 fallback（新 Agent=INSERT 注册行零代码）| 已交付（2026-09-26） | 验收反馈六项修复；方法论回填（methodology_source_id=1）随迁移落库 |
| 迭代 19.11 | Agent Hub 总览页舞台重设计 | [agent-hub-plan.md](agent-hub-plan.md)（D32）：总览改中心枢纽舞台（模拟盘枢纽 + 4 资源站图标卡 + Agent 单元，三层共用 layoutHub）+ 运行态真相源（`AgentOverviewItem.runtime_state` 后端判定：working=collector_log 运行中且 cadence 命中 / produced_today / idle / off 占位）+ 真实数据流连线（复盘→agent、KB/模拟盘按绑定、资讯与情绪→复盘上游，活跃度三档衰减）+ 图例 + Agent 管理收进默认折叠面板；删旧雷达三件套 | 已交付（2026-09-27） | 验收反馈四项；无迁移；working 判定近似（log 无 agent 粒度） |
| 迭代 19.12 | Agent Hub 分层拓扑视图 | [agent-hub-plan.md](agent-hub-plan.md)（D33）：总览改自上而下三层舞台（Agent 运行 / 资源系统五站同维度含 paper 降级普通站 / 基建层五状态灯盒 PostgreSQL·Redis·Celery·掘金柜台·MinIO + Celery 队列分组任务小方框 hover 详情，复用 system status + celery-queues 现成接口零后端改动）+ layoutLayers 分层纯函数 + hubLayout 测试重写 | 已交付（2026-09-27） | 验收反馈三项；纯前端；基建与系统层底座带不画线（多对多密集失焦） |
| 迭代 19.13 | Agent Hub 验收反馈五批 | [agent-hub-plan.md](agent-hub-plan.md)（D34）：风格/策略字段全链路删除（DB 列迁移 + 提示词注入/shared/web 消费点清零）+ 持仓与交易默认成交 Tab + 三会话人设自主化重写 v1.2.0（自主作业体使命/作业循环对齐技能五步/纪律去用户化/人工协同过渡段）+ 复盘 skill 化（per-agent 技能包 REVIEW.md + review_prompt.yaml 回退 trading-default，`load_named_skill_prompt`；输入增补 market_review 盘面语境 + methodology KB 静态层，输出加 market_context/methodology_check 禁默认值，旧缓存 before-validator 兼容）| 已交付（2026-09-27） | 验收反馈四项；迁移 20260927a 先于镜像（DDL 后重启 web/worker）；skill_id/input_hash 未变旧复盘可读 |
| 迭代 19.10 | Agent Hub 验收反馈四批 | [agent-hub-plan.md](agent-hub-plan.md)（D31）：配置页账户区改单 Agent 绑定视图（未绑定弹窗选未占用账户 / 已绑定信息+解绑，全平台列表留系统管理页）| 已交付（2026-09-27） | 纯前端；无迁移 |
| 迭代 19.14 | Agent 会话管理（执行轨迹观测） | [agent-hub-plan.md](agent-hub-plan.md)（D35）：agent_run/agent_run_step 双表 + recorder 独立 session 即写即 commit（异常全吞、单段 8KB 截断/prompt+output 64KB）+ plan/review 服务全程落执行轨迹（precheck/输入组装/KB 检索/LLM 全文/校验/落库步骤序列；缓存命中落 skipped+cache_hit；run_structured meta_out 回填 latency/model 修复历史丢失；collector_log_id 定时链路溯源）+ `GET /admin/agent-runs` 列表/详情 API + web 会话管理页（多条件筛选 + 聊天式时间线详情） | 已交付（2026-09-27） | 验收反馈四项；迁移 20260928a 先于镜像（纯新表）；观测写入与业务事务解耦（failed run 也留轨迹） |
| 迭代 19.9 | Agent Hub 验收反馈三批 | [agent-hub-plan.md](agent-hub-plan.md)（D30）：配置页四区重构（基本配置精简 → 会话人设 YAML 换绑/只读 → 作业技能镜像文件浏览 + 方法论大纲/纪律/知识卡片 → 模拟盘账户）+ `GET /{key}/prompt`·`/{key}/skill/files` 可视化端点 + 会话注入方法论静态层（source_id 入指纹）+ 排程重排（复盘 19:00 / 选股 19:30，只改 cron）+ 活动条目股票名称可点 + plans heldVolume 建仓/增持标注 + 委托/成交 Tabs | 已交付（2026-09-27） | 验收反馈八项；tagline 转可选；无迁移；生产需手动 UPDATE collector_task 两条 cron |
| 迭代 19.8 | Agent Hub 验收反馈二批 | [agent-hub-plan.md](agent-hub-plan.md)（D29）：`GET /{key}/status` 能力端点（方法论源/作业技能 fallback 标签/记忆计数/自动化任务 next+last/近期活动）→ 工作台右栏三卡；Agent CRUD（`POST /agents` 创建即 active + `DELETE /{key}` 级联清理 + `GET /prompt-templates`）→ 总览管理列表「新建 Agent」弹窗与行级删除；plans 行加 stockName（计划行名称+代号）；交易记录 tab 重构「持仓与交易」（资金五指标 + 当前持仓 + 委托/成交，SymbolCell 复用）| 已交付（2026-09-26） | 验收反馈五项；无迁移（纯服务/API/前端） |
| 迭代 20 | F-SIM 批次 8 · 盘中自主执行 | §11（D21-D24 定案，2026-09-28）：`agent-trade-exec` 改**常驻服务**（弃 */5 轮询），四层栈 L0 确定性风控硬校验（仓位/日内笔数，纯函数）→ L1 判断模型概率决策（`SystemOneAdapter` 押注接口契约，D23 封装）→ L2 低置信升级慢模型复核 → L3 人工干预面；慢思考+快反应双模型，早盘/午盘校准（10:20/13:20）；影子模式先行（8a 校准 1-2 周：Jev 主臂 + openjev/Codiv 对照臂，门控阈值 per-vendor 键控）→ 8b active；外部依赖相位（2026-09-28 探针修订）：主臂 = 现有 OpenRouter 账号调生产 Jev（`typesafe/jev-1.13`，透传保真已实证），Codiv/openjev 为对照臂，TypeSafe 直连注册押后（§11.7）。交付切分：**PR-1 执行链骨架已交付**（2026-09-29：迁移 `intraday_exec_mode` 三态替换总闸 + `paper_trade_exec_observation` 逐 tick 观测表 + `agent-intraday-exec` 驻留进程 60s tick，shadow 全链路判断留痕不下单）；**PR-3 精简版执行动态前端已交付**（2026-09-29：`GET /{key}/observations` 只读端点 + 详情页「执行动态」Tab，显著事件默认过滤/全部逐 tick、全天口径 summary、影子 badge，调换先于 PR-2 交付以便影子期人工核查）| 进行中（剩 PR-2 盘中校准：观察报告聚合 + 修正单 + 计划版本化 + 10:20/13:20 heavy 任务） | 依赖迭代 19 多 Agent 基座（已就绪）；下单出口 `execute_agent_order` 与纯函数风控 `evaluate_order_risk` 已内聚共用；影子期达标（1-2 周）后切 active |
| 迭代 21 | F-SIM 批次 9 · 经验沉淀与反哺 | §12：复盘 experiences 自动沉淀 `agent_memory`（表已建；方案 A 定版后只装经验层，方法论基座已 KB 直读）+ 对话记忆工具 + 反哺每日计划 | 未实现 | 依赖批次 6-8 真实运行数据积累（建议 ≥4 周后评估反哺效果） |

**发布门槛**：验收全绿（backend pytest / mypy / ruff，web typecheck / lint / test / build）；新页对照原型走查；develop → main 同步后发布。

## 3. 部署前置与遗留项

- **KB 上生产**：39 个增量 SQL 迁移 + `vector` / `pg_trgm` 扩展；prod KB embedding 回填（`backfill_kb_embedding_from_es.py` 须在 ES 下线前跑完，或 `kb-index` force_rebuild 全量重嵌）；ES 容器与依赖已退役可下线
- **SCF 路由决策复核**：~~`/kb/stream` 视频代理流受 SCF 900s 限制——仅轻量服务器域名提供，SCF Web 函数路由排除~~ → 代理流已整体退役（2026-09-25）：SCF 同步调用响应体上限 ~6MB 本就不可承载媒体，视频/音频改凭证响应内预签名 GET 直链（`playback-token` 附 `streamUrl`），全路由 SCF 可承载
- **KB 验收遗留**：浏览器侧播放器 / 阅读器黄金路径人工验收（本地栈已就绪）
- **KB 产品待定**：侧边栏「知识检索」入口暂撤（`/kb` 页保留，启用时点待定）
- **admin 配置前置**：`llm_config` 登记 embedding / vision 条目并绑定四槽位；asr-1.0 控制台核价回填 `unit_prices`

## 4. 后置池（满足触发条件再立项）

| 项 | 触发条件 |
|----|----------|
| K 线悬浮预览（异动榜行悬浮浮层：日/周/月 K 切换、悬浮即看、点击进详情） | 模拟盘 Agent 闭环（批次 5~9）交付后取回（2026-09-26 主动推迟，优先交易 Agent） |
| F-KB-08 检索测试与运营统计（召回 playground + 运营统计面板） | KB 上生产后出现检索调优 / 运营诉求 |
| KB 权限收敛：Agent 检索工具注入与 `/kb` 消费页按 admin ∪ 白名单门控（需求 04 权限口径；现状为全员注入 + 会话 `use_kb` 开关） | 收敛 KB 开放范围时（普通用户不直接使用知识库） |
| F-SIM 后置：更多智能体类型接入产品化、智能体间对战；公司行为处理（除权除息 / 分红送股） | Agent 闭环（批次 5~9）稳定运行；跨除权持仓统计失真实际显现（需求 07 §7） |
| 用户级模型配置（F-USER-03）、技能广场运营推广 | 多用户开放（注册放开 / 邀请制）；BYOK 与用量治理已随 F-ACCT 交付，终态原型已定稿 |
| 小程序端（Taro） | 移动端访问量显著 |
| F-AI-01 增强：告警驱动产业链再分析 | 链提醒使用率验证 |
| 资金流向显示增强（桑基图 / 迁徙图 / 轮动日历）；研报阅读富交互（inline 预览已交付） | 触发条件成熟再排 |
| 异动检测增强：尾盘急拉（分钟 K）、板块级 MA60 趋势 | 板块快照积累满 60 交易日（约 2026-12）且方法论重新确认 |
| PG 备份入 COS | 硬性排最后 |

## 5. 维护约定

- 状态标注：`未实现` → `实现中（分支）` → `已完成（日期 + PR）`，只在迭代级维护；迭代完成后该行移出待开发表，能力归入 §1 基线一句话，过程内容不回填
- 定时类任务验收惯例：任务目录 API 可见、collector_log 终态、前端展示
- 实现方案见 docs/arch/；调研与实施过程沉淀在代码与提交历史，本文件不回填过程内容
