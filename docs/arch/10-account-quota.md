# 账号准入与 AI 用量治理架构设计

> 闭环：注册改申请 + 管理员审批准入（谁能用）→ 模型调用封装层统一 Token 计量（用多少）→ 配额预扣/结算/耗尽拦截（能用多少）→ 用户自备 Key 出口分流（不占配额）→ 管理端审批/配额调整/用量运营。
> 需求：[docs/requirement/05-account-quota-requirement.md](../requirement/05-account-quota-requirement.md)（F-ACCT-01~05）

## 1. 设计原则

1. **单一出口计量**：全部模型实例的唯一产地是 `build_langchain_model`（`backend/app/agent/runtime/model_factory.py:20`），计量与配额拦截以 LangChain callback 挂在这一处——三类调用入口（助手 SSE / 页面单轮与 skill / Celery 系统任务）自然全覆盖，无散点埋点，新增 AI 能力零成本纳管。
2. **PG 是账本，Redis 是闸门**：配额总量与消耗明细的真相源在 PG（`user_ai_quota` + `user_token_usage`，可重放重算）；Redis 只承载剩余额镜像与原子预扣，键丢失可从 PG 重建，检查路径单次 Lua EVAL。
3. **出口分流在解析层，不在调用层**：`resolve_user_llm` 统一决定本次走 BYOK 还是系统模型，下游工厂/agent 组装对来源无感知。「失败不回退」不是约定而是结构性质——解析之后不存在任何 `except → 默认配置` 代码路径。
4. **计量链路永不阻断主请求**：usage 明细异步批量落库、失败降级记日志；配额闸门在 Redis 故障时降级 PG 校验放行（容忍并发窗口），不 fail-closed 拦死 AI。
5. **存量无感**：迁移一次性 `approved` + 默认配额；`is_active`（管理员禁用）与 `status`（审批状态）语义正交，互不替代。

## 2. 数据模型

迁移 `docker/database/migrations/20260914_account_quota.sql` + `init-scripts/01-schema.sql` 双写（幂等；[03-data-storage](./03-data-storage.md) 规范）。SQLAlchemy 模型对应落 `backend/app/models/`。

| 表/变更 | 键与约束 | 说明 |
|----|----------|------|
| `"user"` 加列 | `status VARCHAR(16) NOT NULL DEFAULT 'approved'` + CHECK `(pending/approved/rejected)`；部分索引 `WHERE status='pending'` | 另加 `application_note` / `reject_reason` / `reviewed_by` FK / `reviewed_at`。DEFAULT 'approved' 使存量行迁移即达标；新注册由服务层显式写 `pending` |
| `user_ai_quota` | `user_id PK FK ON DELETE CASCADE` | `total_tokens BIGINT`，**NULL = 不设上限**（豁免）；`updated_by` + 审计字段。迁移内 `INSERT … SELECT 100000 FROM "user" WHERE status='approved' ON CONFLICT DO NOTHING` 回填存量 |
| `user_token_usage` | idx `(user_id, created_at DESC)`、`(created_at)`、`(feature, created_at)` | 逐次明细：`user_id`（系统维度为 NULL）、`feature CHECK (assistant/page/api_key/system)`、`model_name/provider`、`outlet CHECK (system/byok)`、`prompt/completion/total_tokens`、`estimated BOOLEAN`。累计消耗 = `SUM(total_tokens) WHERE outlet='system'`，是配额已用的可重放来源 |
| `user_llm_config` | `user_id UNIQUE FK ON DELETE CASCADE` | BYOK 配置：`protocol CHECK (openai/anthropic)`、`base_url`、`model_name`、`api_key_encrypted`（Fernet，复用 `app/utils/crypto.py`，与 llm_config 同一加密路径）、`api_key_masked` 冗余脱敏串（读路径免解密）。UNIQUE 物化「同一时间仅一套生效」，删行即回落 |
| `admin_audit_log` | idx `(actor_id, created_at DESC)`、`(action, created_at DESC)` | `actor_id` FK、`action`、`target_user_id`、`detail JSONB`、`ip`。全平台首个审计设施，覆盖审批/配额/全局设置动作 |
| `system_setting` | `key VARCHAR PK` | 运行时可变全局设置 KV：`account.default_quota_tokens`（默认 100,000）/ `account.pending_expire_days`（默认 30）/ `quota.admin_exempt`（默认 true）。管理端可改，故不进 `config.py` |

审计动作清单：`register.approve`（initialQuotaTokens）/ `register.reject`（reason）/ `quota.adjust`（oldTotal/newTotal/delta/scope=adjust|reset）/ `account_setting.update`（key/oldValue/newValue）。

## 3. 计量埋点

### 3.1 模块布局

```
backend/app/services/quota/
├── constants.py            # feature/outlet 枚举、Redis 键模板 quota:remain:{user_id}、缺省值
├── context.py              # MeterContext(user_id|None, feature) + ContextVar + meter_scope()（叶子模块，api/agent/celery 三方共导入）
├── quota_service.py        # precheck / check_and_reserve / settle / invalidate / rebuild（Redis Lua）
├── usage_writer.py         # 异步落库（每条后台任务直写，任意事件循环环境一致）
├── user_llm_service.py     # BYOK CRUD / resolve_user_llm / 连通性测试
└── usage_query_service.py  # 个人明细 + 看板聚合（Asia/Shanghai 分桶）

backend/app/agent/runtime/
├── token_estimator.py      # estimate_text_tokens 纯函数
└── usage_meter.py          # UsageMeterCallback(BaseCallbackHandler)
```

分层：`context.py` 无依赖可被 api 层与 agent 层顶层导入；`usage_meter.py`（agent 层）导入 `services/quota` 合法（agent → services 单向既有方向）。

### 3.2 计量上下文注入

不改 `run_structured` / `skill_runtime` 的调用签名，靠 ContextVar 随 async 上下文传播：

| 入口 | 注入位置 | feature |
|------|----------|---------|
| 助手 SSE `POST /assistant/threads/{id}/runs/stream`（`api/v1/assistant/runs.py`） | 路由层 `_require_thread` 后 `meter_scope(user.id, "assistant")` 包住 event_stream | assistant |
| 页面单轮/skill（chain/analyze、研报摘要、财报摘要、截图识别） | api 路由层调服务前包 `meter_scope(user.id, "page")`，服务层零改动 | page |
| Celery internal 定时 AI | 不显式包裹：**未设置计量上下文的调用由 callback 兜底按 system 维度记账**（无属主即不查配额），免去 runner 接线且杜绝漏计 | system |

`api_key` 类别本期无发射方（F-API-01 用户级 API-KEY 未实装）：枚举与 CHECK 已落位，F-API-01 落地时其鉴权中间件处包 `meter_scope(owner_id, "api_key")` 即纳入。

### 3.3 Callback 机制

`build_langchain_model` 增加关键字参 `meter: bool = True` → `callbacks=[UsageMeterCallback(outlet)]`（outlet 由 cfg 来源决定：`provider='byok'` → byok）；openai 分支同步开启 `stream_usage=True`（langchain-openai ≥1.6 支持，流式拿真实 usage 的前提）。

```python
class UsageMeterCallback(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kw):
        # 读 contextvar meter_ctx；user_id=None(system)/豁免 → 跳过
        # quota_service.check_and_reserve(user_id, estimate) 不足 → 不抛（LangChain 吞
        # callback 异常），照常预扣计量把镜像扣至负值并告警；拦截由入口 precheck 承担
    def on_llm_end(self, response, **kw):
        # 提取 usage_metadata 真实值；无 → prompt 估算 + 输出累积估算，estimated=True
        # quota_service.settle(user_id, reserved, actual)；usage_writer.enqueue(明细)
    def on_llm_error(self, error, **kw):
        # 回补 reserved + 按已收内容估算记 estimated 明细
```

助手多轮工具循环：deepagents 每轮 LLM 调用各触发一次 start/end，**各预扣各结算**，逐轮入账（需求「含工具调用全部轮次」由机制天然满足，无需会话级汇总）。

### 3.4 估算兜底

不引入 tokenizer 库（模型方言不一、依赖重）。`estimate_text_tokens(text)`：CJK 字符记 1 token、其他记 0.25，向上取整；纯函数可单测。仅当协议未回 usage 时使用并打 `estimated=True`，看板展示 estimated 占比。

### 3.5 异步落库

`usage_writer`：每条记录以独立后台任务直写（fire-and-forget，短会话 INSERT）。不使用进程级队列 + flusher：Celery worker 每任务经 `asyncio.run` 起新事件循环，队列与常驻 flush 任务无法跨循环存活；本域写入量级为每次 LLM 调用一条（日千级），逐条短会话写完全够用且在 web / celery / CLI 任意执行环境行为一致。写失败降级记 `usage_write_dropped` structlog 事件（字段完整，供人工补偿）。主请求路径零等待。

## 4. 配额控制

### 4.1 真相源与镜像

- 总量：`user_ai_quota.total_tokens`（管理员调整是唯一写点）。
- 已消耗：`user_token_usage` 中 `outlet='system'` 的 SUM（BYOK 与豁免用户照记明细但不进此口径）。
- 剩余镜像：Redis `quota:remain:{user_id}`；miss / 被失效时由 `quota_service.rebuild(user_id)` 从 PG 重算并 SET（TTL 7 天兜底防泄漏）。

### 4.2 预扣与结算

- 预扣量 = `estimate_text_tokens(prompt)` + `quota_completion_reserve_tokens`（`config.py` 新 Settings 项，默认 1024）。
- `check_and_reserve`：Lua 单脚本把「读-比-扣」合成一次 EVAL——键 nil → 返回重建信号；剩余不足 → 拒绝；命中 → DECRBY 返回余量。单键单脚本 P99 <1ms，满足检查 <10ms。
- `settle(user_id, reserved, actual)`：`INCRBY(reserved - actual)` 回补差额；实际超预扣的部分照扣（余量可为负，下轮即拦）。

### 4.3 拦截、豁免与错误契约

- 豁免（跳过 Redis 仍计量）：`user_id IS None`（system 维度）、`total_tokens IS NULL`、admin 角色且 `system_setting.quota.admin_exempt` 开启。
- 耗尽拦截（双层，入口为主）：① **AI 入口显式 `quota_service.precheck(user_id)`**——助手 runs 流与四个页面生成端点（chain/analyze、研报/财报摘要、截图识别）在调模型前预检，剩余 ≤ 0 直接 REST 429（引导文案：配自有 Key / 联系管理员）；② callback 预扣持续扣减镜像至负值兜底（run 中途打穿的轮次是有限放行窗口，下一个请求必被 ① 拒）。非 AI 功能不经过模型工厂，天然零影响。

### 4.4 配额变更失效链

admin 调整/重置/审批发额 → 写 PG + 审计 + `QuotaService.invalidate(user_id)` DEL Redis 键 → 该用户下一次 AI 调用自动从 PG 重建。无需广播。

### 4.5 并发正确性与故障降级

- 并发：各请求持各自 reserved 份额，Redis 原子扣减保证 `Σ(reserved) ≤ total`；中途崩溃残留的预扣由 TTL 到期重建吸收（重建口径不含未结算预留，宁紧勿超）。
- **Redis 不可达降级**：非豁免用户改查 PG（`total − SUM(usage)`，剩余为正即放行，跳过预扣），容忍并发窗口内少量超支，structlog 告警；豁免与 system 维度照常。对齐项目「Redis 不可达服务降级而非 500」哲学，配额闸门不做 fail-closed（代价是故障期间失去并发防超支保证）。

## 5. BYOK 出口分流

### 5.1 解析层

```python
# services/quota/user_llm_service.py
async def resolve_user_llm(session, user_id: int | None) -> tuple[ResolvedLLMConfig, Literal["system", "byok"]]
    # BYOK 行存在 → 解密构造 ResolvedLLMConfig(provider="byok")；否则 resolve_default_llm
async def save_user_llm_config(...) / clear_user_llm_config(session, user_id)
async def test_user_llm_connection(protocol, base_url, model_name, api_key) -> LlmTestResult
    # httpx 按协议手拼极小请求（复刻 llm_config_service._call_model），timeout 5s、max_tokens 8
```

- 加密复用 `app/utils/crypto.py`（`encrypt_token/decrypt_token/mask_token`），落库密文 + 冗余 masked 串；GET 永不回明文；服务层不把 api_key 放进任何日志字段。
- **vision 路径同走此函数**（截图识别原 `resolve_vision_llm` 调用方改 resolve_user_llm）：BYOK 生效期间单一出口全覆盖；用户模型不支持图片输入则调用直接失败报「自有模型不支持图片输入」，不回退（已知限制，前端文案明确）。

### 5.2 助手 agent 参数化（`assistant_agent.py`）

`_agent` 全局单例 → **LRU 有界缓存**（`OrderedDict`，容量 `quota_agent_cache_size` 默认 8，闲置 TTL 惰性淘汰）：

- 缓存键 `fingerprint = sha256(protocol | base_url | model_name | sha256(api_key) | mcp_tools_version)`。
- `get_assistant_agent(cfg: ResolvedLLMConfig | None = None)`：runs.py 调用前 `resolve_user_llm` 再传入；未传参等价系统默认解析（兼容既有调用点）。BYOK 用户获得独立 agent 实例，LRU 上界防内存膨胀。
- 顺带修复既有缺陷：llm_config 变更后 fingerprint 变化自然重建（现状仅 MCP 变更触发 reset）。
- checkpointer 仍全局单例共享；subagents 声明不指定 model、继承主模型，自动同出口。

### 5.3 单轮与 skill 路径

- `run_structured`（`agent/runtime/structured.py`）签名加 `user_id: int | None = None`：内部 `resolve_user_llm` 替换 `resolve_default_llm`；api 调用方传 `user.id`，Celery 路径不传。仅此一处签名变更。
- 页面 skill 工厂（`agent/skills/*_agent.py`）加 `cfg` 入参（per-call 构建，本无缓存问题），入口服务先 resolve 再构建；`skill_runtime` 签名不变。
- 清除 BYOK：删行后下一次解析自然回落（解析层无缓存）；旧 fingerprint 的 agent 等 LRU/TTL 淘汰，不主动清理。

### 5.4 失败不回退

`resolve_user_llm` 之后不存在任何回退路径；BYOK 端点的无效 Key / 欠费 / 限流错误原样上抛——REST 直接报错，助手 SSE 走 error 帧，文案附「请检查我的模型配置」。杜绝静默烧系统预算。

## 6. 注册审批流

### 6.1 注册语义变更

`POST /auth/register`（`api/v1/auth.py`）改提交申请：请求体加可选 `application_note`；

- 同 username/email 存在 **pending** → 409「已有申请在审」；
- 同 username/email 存在 **rejected** → **复用该行重置回 pending**（新密码哈希/新说明/清 reject_reason）——驳回不永久占位，用户零求助重新申请；
- 新建 `status='pending'`，**不签发 JWT**，201 返回 `RegisterAccepted { message }`（wire camelCase，shared/types 同步改型）。

IP 限流照抄 `login_throttle` 模式：键 `auth:register:ip:{ip}`（INCR + EXPIRE 86400，默认 5 次/天，`auth_register_ip_limit` 可配；RedisError fail-open + 限频告警），超限 429。

### 6.2 登录/认证双拦截

- `attempt_login`（`services/user/user_service.py`）：密码与 `is_active` 校验之后——pending → 403 `AUTH_PENDING`（「账号待审批，请等待管理员开通」）；rejected → 403 `AUTH_REJECTED`（附 reject_reason）。异常仿 `LoginLockedError` 结构化范式。
- `get_current_user`（`dependencies/__init__.py`）：`is_active` 旁增 `status != 'approved'` → 401 同款 code（防御纵深：审批前不可能有 token，但覆盖后续状态回退）。

### 6.3 审批台与惰性过期

`services/admin/approval_service.py`：

```python
async def list_pending(session) -> list[PendingApplication]   # 含惰性清理
async def approve(session, admin, user_id, initial_quota_tokens: int | None) -> None
    # status→approved + 建 user_ai_quota（缺省取 system_setting）+ 审计
async def reject(session, admin, user_id, reason: str) -> None  # reason 必填 + 审计
async def pending_count(session) -> int                       # 角标，顺带清理
```

**pending 过期用惰性清理而非 Celery 任务**：`list_pending` / `pending_count` / 注册冲突检查三个入口顺手 DELETE `status='pending' AND created_at < now − N 天` 的行。审批台低频打开的场景下零调度成本且效果等价，不为此新增定时任务（YAGNI）。

## 7. API 面与前端

### 7.1 端点清单（wire camelCase；query snake_case）

个人侧（挂 `users.py` 的 `/users/me/*` 命名空间，超行数拆文件）：

| 端点 | 说明 |
|------|------|
| `GET /users/me/quota` | `{totalTokens, usedTokens, remainingTokens, unlimited, byokEnabled}` |
| `GET /users/me/usage?feature=&limit=` | 消耗明细 + 按 feature 分组汇总 |
| `GET /users/me/llm-config` | masked 视图（404 = 未配置），永不回明文 |
| `PUT /users/me/llm-config` | 保存（前端先调 test 再提交，服务端不重复测试） |
| `POST /users/me/llm-config/test` | 草稿参数连通性测试（不落库） |
| `DELETE /users/me/llm-config` | 清除即回落系统模型 |

管理侧（`api/v1/admin/`，均 admin 依赖 + 审计）：

| 端点 | 说明 |
|------|------|
| `GET /admin/users`（扩展） | 响应加 `status/applicationNote/rejectReason/remainingQuota/totalUsed/byokEnabled`；支持 `status=pending` 过滤 |
| `POST /admin/users/{id}/approve` | body `{initialQuotaTokens?}` |
| `POST /admin/users/{id}/reject` | body `{reason}`（必填） |
| `POST /admin/users/{id}/quota` | body `{action: adjust|reset, deltaTokens?}`（正追加负核减 / 重置全局默认） |
| `GET /admin/users/pending-count` | 待审角标 |
| `GET /admin/usage/dashboard?days=30` | 日/周趋势、Top 用户、按 feature 与 model 分布、estimated 占比、耗尽用户数（`(created_at AT TIME ZONE 'Asia/Shanghai')::date` 分桶，时间戳 aware UTC） |
| `GET/PUT /admin/settings/account` | 三项全局设置 |

### 7.2 错误码契约

| code | HTTP | 场景 | 引导 |
|------|------|------|------|
| `QUOTA_EXHAUSTED` | 429 | REST（页面单轮/skill）与 SSE | 「配额已用尽：前往设置配置自有模型，或联系管理员追加」 |
| `AUTH_PENDING` / `AUTH_REJECTED` | 403 | 登录 | 待审提示 / 未通过 + 原因 |

SSE 形态：runs.py except 分支识别 `QuotaExhaustedError` → `sse_event("error", {error_code: "quota_exhausted", status_code: 429, message: 引导文案})`；前端 SSE error 处理按 `error_code` 分流——配额耗尽弹「去配置自有模型」跳设置页，BYOK 失败弹「检查我的模型配置」。

### 7.3 前端改动面

| 位置 | 改动 |
|------|------|
| `web/src/pages/Register/Register.tsx` | 成功改待审批回执视图（不 authLogin、不跳转） |
| `web/src/pages/Login/Login.tsx` | 403 code 分支 Alert（待审 / 驳回原因） |
| `web/src/pages/Settings/Settings.tsx` | SECTIONS 加「配额与用量」「我的模型」两锚点区；`QuotaSection.tsx`（剩余额进度 + 按 feature 消耗）、`MyModelSection.tsx`（协议/base_url/model/api_key 表单，draft-test 范式抄 `Admin/McpServers/McpServerModal.tsx`） |
| `web/src/pages/Admin/Users/Users.tsx` | 状态/剩余配额/累计消耗/BYOK 列 + `ApproveModal` / `QuotaAdjustModal` / `UsageDrawer` |
| `web/src/pages/Admin/UsageDashboard/` | 新页；router.tsx + Sidebar ADMIN_MENU_ITEMS + Admin.tsx ADMIN_LINKS 三处注册 |
| Sidebar 角标 | `usePendingApprovalBadgeCount`（300s 轮询，复刻 `useCollectorHealthBadgeCount` 范式） |
| shared 契约 | `shared/types/account.ts` 新增（AccountStatus/QuotaInfo/UsageRecord/UserLlmConfig/RegisterAccepted）、`api.ts` 注册响应改型、`shared/api/endpoints.ts` 补端点、`web/src/api/mappers/account.ts` 镜像 |

## 8. 验证

- 单测（`backend/tests/unit/`）：`token_estimator`（CJK/ascii/空串）；`usage_meter`（usage 提取 / 估算 estimated / error 回补 / ContextVar 经 astream 传播）；`quota_service`（reserve 不足/命中/重建、settle 回补与超支、invalidate；fakeredis + Lua）；`user_llm_service`（加密往返 / BYOK>默认优先级 / 清除回落）；`register_approval`（pending 409 / rejected 重报 / 双拦截 / 惰性过期 / IP 限流）；`agent_cache`（fingerprint 键 / LRU 淘汰 / 配置变更换代）；`audit`（动作 detail 落库）。
- docker 栈走查：新注册→回执→审批前登录被拒→审批→登录→个人页 10 万配额→助手一轮对话配额实时扣减→耗尽后 AI 拦截且行情/资讯正常→配 BYOK 后配额不动、坏 Key 直接报错不回退→看板有数→待审角标出现→存量用户自动 approved。
- 质量门：backend `uv run mypy app/`、`ruff check .`、`pytest -m unit`；web typecheck / lint / test / build。

## 9. 风险与边界

1. **agent 单例改 LRU 的 SSE 回归**：per-user 实例改变「图全局唯一」假设——三通道流（messages/updates/custom）、HITL resume、cancel 全链路回归；MCP 工具集版本进 fingerprint 防「不同工具集复用旧图」。
2. **流式 usage 协议差异**：openai 兼容网关不支持 stream_usage 时恒为 estimated；kimi（anthropic 协议 message_delta）/ deepseek / zhipu 的 usage_metadata 可得性需实测钉死。
3. **ContextVar 传播与 callback 异常上抛**：async 任务继承上下文需单测钉死；`QuotaExhaustedError` 须沿 run_manager 上抛至 `astream` 调用方而不被 deepagents 循环吞掉。
4. **api_key 预留类别**：枚举/DDL/看板均已落位、无发射方；F-API-01 落地时只加中间件注入。
5. **usage 表增长**：个人部署量级（日千级）无忧；月分区与看板预聚合留作后续演进，不预建。
6. **BYOK 模型能力差异**：不支持图片输入/结构化输出的用户模型会调用失败——按失败不回退原则直接报错，属预期行为。

## 10. 后续文档索引

- [03-data-storage.md](./03-data-storage.md) — 表命名约定与幂等迁移双写规范
- [04-ai-agent.md](./04-ai-agent.md) — 模型工厂、deepagents runtime 与 SSE 事件链
- [05-web-frontend.md](./05-web-frontend.md) — 设置页锚点分区与后台管理页组织
- [06-deployment.md](./06-deployment.md) — 部署拓扑与配置注入
