# 部署演进计划（现状 → 目标架构实施路线）

> 状态：评估中（2026-08-30）。目标架构设计见 `docs/arch/06-deployment.md`，本文档维护从现状到目标的实施路线、验证关卡与成本评估。

## 1. 现状（方案 A：轻量服务器全栈单机）

生产环境为腾讯云轻量应用服务器（Lighthouse 2C4G/50G，ap-beijing，`49.233.145.117`），域名 `invest.17aitech.com`（已备案）→ Caddy 反代。代码位于 `/opt/investment`（develop 分支），`COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml` 两文件叠加。

| 分组 | 容器 | 说明 |
|------|------|------|
| 基础设施 | postgres(timescale)、redis、elasticsearch、minio、milvus、etcd | bind mount 至 `workspace/`；**milvus/etcd 代码零引用，属闲置** |
| 应用 | web（nginx+FastAPI 合一镜像 :9000） | SPA + API 同端口，Caddy → web:9000 |
| 调度 | celery-beat + worker-realtime/batch/heavy | 调度真相源为 `collector_task` 表，beat 周期同步 DB |

已知问题（2026-08-30 部署实践暴露）：

1. **远程构建慢**：2C4G 上构建 web 镜像（vite）分钟级到十几分钟，依赖层失效时可达 1.5 小时；曾因 vite 构建内存耗尽导致整机换页僵持失联 30+ 分钟
2. **内存上限低**：4GB 已被 12 容器占满，无法再承载新服务
3. **部署靠手工 SSH**：git pull → compose build → up -d，GitHub CI 流水线未实际启用（TCR 推送 secrets 未验证）

## 2. 演进路线

| 阶段 | 内容 | 解决 | 风险 | 状态 |
|------|------|------|------|------|
| Phase 1 | CI/CD：Actions 构建 → TCR → 服务器手动 pull 部署 | 问题 1/3 | 低 | **已完成（2026-08-31 验收全绿）** |
| Phase 2 | 瘦身：下线 milvus/etcd；MinIO→COS；worker 3→2 收缩 | 问题 2 | 低 | 待实施 |
| Phase 3 | Web API → SCF Web 函数（爬虫任务留置轻量） | 问题 2 | 中，有两道验证关卡 | 评估中 |
| Phase 4 | SPA → EdgeOne Pages；Agent Runtime 承载 deepagents（助手对话主承载，摆脱 SCF 900s） | 前瞻 | 有三道前置验证关卡 | 评估结论已定（2026-08-30） |
| Phase 5 | PG 备份入 COS：`pg_dump` 定时任务推对象存储 | 数据安全 | 低 | 后置（排在全部开发计划之后，2026-08-31 用户明确） |

> 各阶段验证方法见对应章节；每次落地后统一以 [06-deployment.md §4.3 验收清单](../arch/06-deployment.md) 为基线回归。

## 3. Phase 1：CI/CD 流水线

GitHub Actions（`.github/workflows/ci.yml`，develop push 触发 + workflow_dispatch 手动）：

1. **构建推送**：按 [06-deployment.md §3 镜像与发布](../arch/06-deployment.md) 构建推送 `web-api` / `collector` 双镜像（linux/amd64，tag = `latest` + git short sha）
2. **凭据**：repo secrets `TCR_NAMESPACE` / `TCR_USERNAME`（腾讯云 UIN）/ `TCR_PASSWORD`（**推送至今未验证成功，Phase 1 第一项就是打通它**）
3. **compose 镜像定位（前置，已实施）**：应用服务 `image:` 指向 TCR（`web-api` / `collector` 双镜像，beat 与 workers 共用 collector），tag 走 `${APP_TAG:-latest}`——服务器 `.env` 以 `APP_TAG` 钉版（填 CI 输出的 git 短 sha），缺省 `latest`；生产不用裸 `latest` 做部署指针（不可复现）。`build:` 保留，供本地与 §7 应急构建
4. **部署（手动）**：CI 不含任何部署 job；服务器一次性 `docker login ccr.ccs.tencentyun.com`。发布 = `.env` 写入本次短 sha → `docker compose pull && docker compose up -d --wait --remove-orphans --no-build`（`--wait` 借 healthcheck 作部署闸门、失败非零退出；`--remove-orphans` 为 Phase 2 下线服务自动清孤儿容器；`--no-build` 防误在服务器构建）。回滚 = `.env` 改回上一 sha 重跑同命令。定期 `docker image prune -f` 控制旧镜像盘占。发布节奏自控，不引入 SSH action / watchtower

效果：服务器不再执行任何构建（僵持事故根因根除），仅做镜像拉取与启动；合并即产出新镜像，上线时机由人工控制。远程构建流程仅作为 CI 故障时的应急手段保留（见 §7）。

验证：`workflow_dispatch` 手动触发一次流水线 → Actions 全绿、TCR 出现双镜像新 tag → 登录服务器手动 pull 部署后按 [06-deployment.md §4.3 验收清单](../arch/06-deployment.md) 回归（health / worker ping / 任务目录）。

实施记录（2026-08-31，验收全绿）：

- 双镜像并行 job + 推送 stall 步骤级超时（25/30 分钟）+ 自动重试 + `provenance: false`；跨镜像 GHA cache 复用使第二个镜像构建秒级
- **推送 TCR 避开北京时间晚高峰（约 20:00-24:00）**：实测 19:55 推送成功、20:47 起四连 stall（token 认证后零进展）、次日 07:33 错峰重推秒过——美国 runner → 北京 TCR 个人版的跨境拥塞是概率性根因，失败重跑即可，无需改架构
- 服务器 daemon 的阿里云镜像加速对部分 Docker Hub 镜像返回 403：minio 钉住版本拉不动，用本地在跑镜像 retag 兜底（Phase 2 下线前不再升级）
- 首次 pull 部署：web/beat/3 workers 全部切换 TCR 镜像 `654715b`，health / 域名 200 / 3 worker ping 全绿，基础设施容器零扰动

## 4. Phase 2：轻量服务器瘦身 + COS

| 动作 | 依据 | 效果 |
|------|------|------|
| 下线 milvus + etcd | 代码仅 `app/core/config.py` 出现，无任何业务引用 | 释放约 2GB 内存 |
| MinIO → COS | COS 提供 S3 兼容端点，应用侧仅改 endpoint + 密钥；对象用 COS Migration 工具搬迁 | 释放 MinIO 内存，文件存储转托管 |
| worker 收缩 3→2 | realtime 与 batch 合并为单 worker（`-Q realtime,batch`，Celery 按列举顺序消费；batch 定点盘后、realtime 盘中，时间窗天然错开互不挤占）；**heavy 保持独立容器且并发=1**——LLM 分钟级任务（复盘/归因）不得占用通用采集池 | 释放约 200-400MB；队列仍为 3 条，仅容器数收缩 |
| ES 暂留并盘用量 | 新闻搜索 + 知识库在用 | 后续决定升云 ES 或降级 PG 全文检索 |

验证：每项动作落地后按 [06-deployment.md §4.3 验收清单](../arch/06-deployment.md) 回归；`free -h` 核对内存释放与上表"效果"相符；COS 切换后应用走通一次研报/财报文件读写（PG 备份任务后置，见 §7）；worker 合并后双容器 `inspect ping` 应答、`collector_log` 无积压。

## 5. Phase 3：Web API → SCF Web 函数（先过验证关卡）

定位：仅迁移 Web API（SPA 另行走 EdgeOne，见 Phase 4）；**Celery 全家桶与全部采集任务留置轻量服务器**，理由：

- **900 秒硬上限**：SCF 最大执行时长 900s，概念成分采集实测约 22 分钟，超限且不宜拆分（全有或全无语义）
- **WAF 出口稳定性**：东财 WAF 按 TLS 指纹 + 主机限流，SCF 共享出口 IP 池风险高于轻量服务器固定出口 IP
- PG/Redis 本就驻留轻量，worker 与数据同机时延最低

### 5.1 验证关卡（两道，任一不过则放弃或延期）

1. **网络**：轻量服务器不能直接加入自定义 VPC，但可通过**云联网 CCN** 打通：轻量控制台「内网互联」关联云联网 → SCF 绑定同地域 VPC → VPC 关联该云联网（同地域免费）。需控制台实操验证 SCF 内网可达 PG/Redis
2. **流式**：SCF Web 函数官方支持 SSE（AI 生成场景），但须实测助手流式对话经函数 URL 入口的空闲超时表现（社区有网关层提前断连案例），并确认 LLM 长响应（实测归因约 90s）在 900s 内稳定

### 5.2 迁移要点

- Web 函数沿用 [06-deployment.md §1](../arch/06-deployment.md) 定义的一体镜像与规格；API 网关触发器方案作废（该产品 2025-06-30 停服），入口用函数默认域名 / 自定义域名
- **冷启动**：镜像函数初始化默认 90s，个人低频使用需预置并发（1-2 实例）保体验——这是本阶段主要成本项，也是"是否值得迁移"的核心权衡
- Caddy 保留为 COS/MinIO 兼容层撤除后的过渡入口或直接下线

### 5.3 迁移后验收

两道关卡通过并完成切换后，以 [06-deployment.md §4.3](../arch/06-deployment.md) 为基线回归：域名 `/health` 200、助手流式经函数 URL 稳定出 token、预置并发下首请求体验可接受。观察期内保留回退能力（入口切回轻量服务器），稳定后再下线旧链路。

## 6. Phase 4：EdgeOne（评估结论已定，2026-08-30）

- **SPA → EdgeOne Pages（免费静态托管档）**：定位是**静态托管**而非"全球加速"。SPA 公网唯一出口后，静态请求不再占 SCF 并发实例与调用计费，且 SPA 发版与 API 解耦（`/assets/` 内容哈希长缓存 + `index.html` 禁缓存，发版即生效）；域名已备案可直接接入；`VITE_APP_VERSION` 由 CI 注入。web-api 一体镜像保留 nginx 静态兜底（服务本地 compose / 灾备）
- **EdgeOne Agent Runtime = 助手对话运行时主承载**（deepagents / LangGraph）：会话独占沙箱、毫秒级冷启动。**900s 是 SCF 函数执行上限，对话迁入沙箱后不再适用**；边缘档单次执行上限 3600s、会话空闲 300s，对话分钟级场景余量充足；配额形式为沙箱数量 + 沙箱回收时间（可提工单调整）。沙箱内回调核心 API 取数，不直连数据库
- **长时 Agent 升级路径**：若未来出现 >1h 的长任务（如深度研报告成），升级到腾讯云 Agent Runtime（云端独立产品 AGS，会话持续运行最长 7 天、暂停保留 30 天且暂停期间不收费、冷启动约 100ms），与边缘档是两个产品形态
- **前置验证关卡（三道，实施前实测）**：
  1. SSE 流式经 Agent Runtime 入口的透传与空闲超时表现
  2. deepagents / LangGraph 依赖在沙箱镜像内的兼容性与镜像体积
  3. 沙箱数量 / 回收配额对多会话并发的满足度
- **实施后验收**：以 [06-deployment.md §4.3](../arch/06-deployment.md) 为基线——流式对话经 Agent Runtime 入口正常出 token、可中断；SPA 经 Pages 域名访问、`/assets/` 命中长缓存且发版即生效
- 与 Phase 1-3 解耦，不阻塞

## 7. Phase 5（后置）：PG 备份入 COS

`pg_dump` 定时任务产出备份并上传对象存储，解决单机数据风险。实施内容：collector 镜像内置 `pg_dump` 客户端（PGDG 源装 postgresql-client-16）、备份任务模块（subprocess 导出 → MinIOService 上传，S3 兼容协议天然支持 COS）、TASK_SPECS 注册与调度。

**实施时机：排在全部开发计划最后**（2026-08-31 用户明确，Phase 2 不含此项）。

验证：`pg_dump` 任务在 COS 产出当日备份对象，恢复演练一次（对象下载 → 空库恢复 → 行数抽查）。

## 8. 应急构建流程（CI 不可用时）

服务器上构建必须按安全流程执行，否则 web 镜像 vite 构建会耗尽内存导致整机僵持（sshd 不应答、HTTP 全死，控制台软重启信号僵持下迟迟不生效）：

```bash
cd /opt/investment
sudo docker compose stop elasticsearch web celery-beat celery-worker celery-worker-heavy  # 留 pg/redis/minio/caddy
sudo docker compose build web                     # 先 web（内存大户）
sudo docker compose build celery-beat celery-worker celery-worker-heavy
sudo docker compose up -d                          # 全量拉起
```

构建日志放 `/home/ubuntu/`（/tmp 重启即丢）；依赖锁未变时层缓存生效，全程约 10 分钟。

## 9. 成本对比（估算，待控制台核实）

| 项 | 现状（方案 A） | 目标架构后 |
|----|---------------|-------------------|
| 轻量服务器 2C4G | 现有合约 | 现有合约（角色收缩为数据+任务主机） |
| SCF Web 函数（预置并发 1×2048MB） | — | 约 ¥70-150/月 |
| COS 存储 + 流量 | — | 约 ¥10-30/月（个人量级） |
| EdgeOne Pages | — | 免费额度内 |
| EdgeOne Agent Runtime | — | 免费档额度内（单次执行上限 3600s，长时升级云端 AGS 另计） |
| TCR 个人版 | — | 免费额度内 |

结论：目标架构总成本与现状基本持平略升，核心收益是**发布自动化、机器瘦身可扩展、文件与 Agent 层转托管**，而非省钱。
