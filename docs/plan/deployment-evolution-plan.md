# 部署演进计划（现状 → 目标架构实施路线）

> 状态：评估中（2026-08-30）。目标架构设计见 `docs/arch/06-deployment.md`，本文档维护从现状到目标的实施路线、验证关卡与成本评估。

## 1. 现状（方案 A：轻量服务器全栈单机）

生产环境为腾讯云轻量应用服务器（Lighthouse 2C4G/50G，ap-beijing，`49.233.145.117`），域名 `invest.17aitech.com`（已备案）→ Caddy 反代。代码位于 `/opt/investment`（develop 分支）。本地开发与生产是**两套互相独立的 compose 文件**：`docker-compose.yml` = 本地（含 minio 对象存储、端口全发布、无 caddy/https），`docker-compose.prod.yml` = 生产（COS 对象存储无 minio 容器、caddy 80/443、应用镜像走 TCR）。compose 默认只加载 `docker-compose.yml` 这一个文件名，生产命令一律显式 `docker compose -f docker-compose.prod.yml …` 指定（`-f` 优先级高于 `.env` 的 `COMPOSE_FILE`；生产机上 up/pull/down/restart 裸跑会误用本地文件）。

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
| Phase 2 | 瘦身：下线 milvus/etcd；MinIO→COS；worker 3→2 收缩 | 问题 2 | 低 | **已完成（2026-08-31 验收全绿，含 MinIO→COS 迁移）** |
| Phase 3 | Web API → SCF Web 函数（爬虫任务留置轻量） | 问题 2 | 中，有两道验证关卡 | **关卡验证全绿（2026-08-31），入口已切函数 URL** |
| Phase 4 | SPA → EdgeOne Pages 静态托管；Agent Runtime 承载助手对话（摆脱 SCF 900s） | 前瞻 | — | **已取消（2026-09-01，见 §6）** |
| Phase 5 | PG 备份入 COS：`pg_dump` 定时任务推对象存储 | 数据安全 | 低 | 后置（排在全部开发计划之后，2026-08-31 用户明确） |

> 各阶段验证方法见对应章节；每次落地后统一以 [06-deployment.md §4.3 验收清单](../arch/06-deployment.md) 为基线回归。

## 3. Phase 1：CI/CD 流水线

GitHub Actions（`.github/workflows/ci.yml`，develop push 触发 + workflow_dispatch 手动）：

1. **构建推送**：按 [06-deployment.md §3 镜像与发布](../arch/06-deployment.md) 构建推送 `web-api` / `collector` 双镜像（linux/amd64，tag = `latest` + git short sha）
2. **凭据**：repo secrets `TCR_NAMESPACE` / `TCR_USERNAME`（腾讯云 UIN）/ `TCR_PASSWORD`（**推送至今未验证成功，Phase 1 第一项就是打通它**）
3. **compose 镜像定位（前置，已实施）**：应用服务 `image:` 指向 TCR（`web-api` / `collector` 双镜像，beat 与 workers 共用 collector），tag 走 `${APP_TAG:-latest}`——服务器 `.env` 以 `APP_TAG` 钉版（填 CI 输出的 `<分支>-<短 sha>`，如 `develop-4cdc1b7`），缺省 `latest`；生产不用裸 `latest` 做部署指针（不可复现）。`build:` 保留，供本地与 §7 应急构建
4. **部署（手动）**：CI 不含任何部署 job；服务器一次性 `docker login ccr.ccs.tencentyun.com`。发布 = `.env` 写入本次 tag（分支-短 sha）→ `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d --wait --remove-orphans --no-build`（`--wait` 借 healthcheck 作部署闸门、失败非零退出；`--remove-orphans` 为 Phase 2 下线服务自动清孤儿容器；`--no-build` 防误在服务器构建）。**写操作命令必须带 `-f docker-compose.prod.yml`**——裸命令落到 `docker-compose.yml`（本地文件），会重新拉起 minio 并把 caddy 当 orphan 摘除。回滚 = `.env` 改回上一 tag 重跑同命令。定期 `docker image prune -f` 控制旧镜像盘占。发布节奏自控，不引入 SSH action / watchtower

效果：服务器不再执行任何构建（僵持事故根因根除），仅做镜像拉取与启动；合并即产出新镜像，上线时机由人工控制。远程构建流程仅作为 CI 故障时的应急手段保留（见 §7）。

验证：`workflow_dispatch` 手动触发一次流水线 → Actions 全绿、TCR 出现双镜像新 tag → 登录服务器手动 pull 部署后按 [06-deployment.md §4.3 验收清单](../arch/06-deployment.md) 回归（health / worker ping / 任务目录）。

实施记录（2026-08-31，验收全绿）：

- 双镜像并行 job + 推送 stall 步骤级超时（25/30 分钟）+ 自动重试 + `provenance: false`；跨镜像 GHA cache 复用使第二个镜像构建秒级
- **推送 TCR 避开北京时间晚高峰（约 20:00-24:00）**：实测 19:55 推送成功、20:47 起四连 stall（token 认证后零进展）、次日 07:33 错峰重推秒过——美国 runner → 北京 TCR 个人版的跨境拥塞是概率性根因，失败重跑即可，无需改架构。拥塞也可能连续数小时（实测两轮 4+4 次尝试全 stall）；此时兜底走本地 `docker buildx --platform linux/amd64 build --push` 直推 TCR（国内出网 48-52s），服务器 `APP_TAG` 钉该 tag（分支-短 sha）即可
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

实施记录（2026-08-31，PR #5 合并后当日部署，验收全绿）：

- 代码：worker 合并 `celery-worker`（`-Q realtime,batch`，entrypoint 节点名取首队列）+ `celery-worker-heavy` 改名对齐 arch 终态；milvus/etcd 从双 compose、config.py、init-scripts、skill 描述全链路清除；`.env.example` 规范化重构，调优常量默认值下沉 compose `${VAR:-默认}`；本地栈 8 容器全 Healthy 验证
- 服务器：`.env` 备份后清 10 行旧 CELERY 常量并钉 `APP_TAG=08266dc` → 定向 `pull` 四应用镜像（避开 minio 镜像源 403）→ `up -d --wait --remove-orphans --no-build`；9 容器全 Healthy，`realtime@`/`heavy@` 双节点 ping OK，域名 `/health` 200，beat 分钟级调度正常
- 资源：内存可用约 446Mi → 1.3Gi；删 milvus/etcd 镜像释放约 2.5G 磁盘（avail 16G）；上一版 `654715b` 镜像保留供一步回滚

MinIO→COS 切换记录（2026-08-31 当日完成，验收全绿）：

- **minio-py 走 path-style 会被 COS 拒绝**（`PathStyleDomainForbidden`，SDK 仅对 AWS/aliyuncs 自动 virtual-host）：新增 `MINIO_VIRTUAL_HOST` 配置，开启后对两个 client 调用 `enable_virtual_style_endpoint()`；endpoint 填**区域域名**（`cos.ap-beijing.myqcloud.com`，SDK 自动把 bucket 前置到主机名，勿填 bucket 域名否则双重前缀）；另 COS 签名必需显式 `MINIO_REGION`
- **迁移**：以旧 web 容器（minio-py 7.2.20 已含 virtual-host API）跑拷贝脚本，src=旧 minio（path-style）→ dst=COS（virtual-host），690 对象 / 542MiB 零错误；抽样权威比对原始 etag == COS etag（md5）逐字节一致——MinIO 磁盘 `part.1` 比对象多 32 字节系 bitrot 附加物，非内容
- **验收**：容器内 upload → 预签名（virtual-host 域名 + SigV4）→ download roundtrip；真实研报预签名 URL 从公网 curl 200（482841B application/pdf）；`--remove-orphans` 摘除 minio 容器后 8 容器全 Healthy、health 200、双 worker pong、beat 正常；`workspace/minio` 数据目录保留兜底
- **部署插曲**：TCR 跨境推送连续 stall 时，本地 `docker buildx --platform linux/amd64 build --push` 直推 TCR（国内出网秒级，48-52s）；服务器访问 GitHub 中断不阻塞部署（应用代码全在 TCR 镜像内，仓库副本仅作 compose 编排）

## 5. Phase 3：Web API → SCF Web 函数（先过验证关卡）

定位：仅迁移 Web API（SPA 维持同源一体承载，原静态拆分已取消，见 §6）；**Celery 全家桶与全部采集任务留置轻量服务器**，理由：

- **900 秒硬上限**：SCF 最大执行时长 900s，概念成分采集实测约 22 分钟，超限且不宜拆分（全有或全无语义）
- **WAF 出口稳定性**：东财 WAF 按 TLS 指纹 + 主机限流，SCF 共享出口 IP 池风险高于轻量服务器固定出口 IP
- PG/Redis 本就驻留轻量，worker 与数据同机时延最低

### 5.1 验证关卡（两道，任一不过则放弃或延期）

1. **网络**：不走云联网/VPC——SCF 不绑 VPC 即默认具备公网出口，直连轻量公网 IP 的 PG/Redis。前置改造（2026-08-31 已落 `feat/phase3-scf`）：生产 compose 发布 PG 5432 / Redis 6379、Redis 以 `REDIS_PASSWORD` requirepass 启动（compose 硬必需，漏配拒启，连接串同步改带密码）；轻量控制台防火墙放行 5432/6379 后从 SCF 实测可达。ES 无认证不发布（新闻搜索/知识库端点迁移期不可用，后续随 ES 云化或降级另议）
2. **流式**：SCF Web 函数官方支持 SSE（AI 生成场景），但须实测助手流式对话经函数 URL 入口的空闲超时表现（社区有网关层提前断连案例），并确认 LLM 长响应（实测归因约 90s）在 900s 内稳定

实施记录（2026-08-31，两道关卡验证全绿，入口已切函数 URL `webapi.17aitech.com`）：

- **网络关卡**：生产 compose 发布 PG 5432 / Redis 6379 + Redis requirepass（`REDIS_PASSWORD` 为 compose 硬必需，漏配拒启；连接串改引用式，密码只存一份），轻量防火墙放行两端口后 SCF 直连公网 IP 实测可达；`/api/v1/market/indices` 200 + 带密码 Redis GET（无兜底调用）随同一请求通过
- **SCF 控制台环境变量两个坑**（均曾致函数不可用）：① 连接串笔误（端口 `:5432:5432`）令 pydantic Settings 导入即崩，uvicorn 被 supervisor 反复拉起（~13s 循环），网关返回 502；② 控制台**不做 `${...}` 引用替换**（compose 特性），照抄 `.env.example` 引用式写法则密码成为字面量——应用正常启动但 PG 认证失败，服务器 PG 日志 `password authentication failed` 为判别特征。诊断链：响应头 + 函数日志 traceback → 控制台修正
- **流式关卡**：助手 SSE 经函数 URL 实测 496 个 token 增量块 25.4s 持续到达（首字节 0.59s），无网关缓冲倾倒，`event: end` 正常收尾、会话落库成功；90s 级长任务与实测同机制，900s 预算余量充足
- **规格定版（实测）**：实例内存基线 ~527MB（uvicorn 单 worker 一体镜像）；**1024MB 下 8 路行情接口并发突发即杀实例**（60-100ms 极速 502、~13s 重启循环，登录页即可触发），而 `/health` 8 并发全绿证明扩容正常、瓶颈在单实例内存——提至 **2048MB** 后 3 波 × 8 接口 24/24 全 200（0.08-1.19s）。超时 900s；预置并发 1-2 实例建议设置（消除闲置回收后首次请求冷启动）
- **下线旧链路 + 冷启动实测（2026-09-01）**：服务器 `compose stop web caddy`（保留 6 容器：pg/redis/es/beat/双 worker，内存可用 910Mi → 1.3Gi），随后 web/caddy 定义已从 `docker-compose.prod.yml` 移除（compose 仅余 6 服务），下次发布 `--remove-orphans` 自动清掉两个已停容器；回退 = 从 git 历史恢复两服务定义 + `up -d web caddy` + DNS 切回（TCR web-api 镜像与服务器本地 caddy 镜像保留勿 prune）。
- **集合端点 307 混合内容修复（2026-09-01）**：前端 4 个 list 端点（research / financial-reports / hotspot / fund-flow）不带尾斜杠而后端路由为 `@router.get("/")`，FastAPI redirect_slashes 的 307 Location 在 SCF 全 http 转发链 + uvicorn 未开 proxy-headers 下生成 `http://`，HTTPS 页面追随即被浏览器按混合内容拦截——研报/财报/热点/资金流向四个列表页空白，**均与 ES 无关**（列表全走 PG）。修复（双管齐下）：容器 nginx 对 uvicorn 各转发 location 无条件 `proxy_set_header X-Forwarded-Proto https` + supervisord uvicorn 加 `--proxy-headers --forwarded-allow-ips="*"`（最小应用实测 Location 随该头切换 scheme）；shared 前端 list 端点补尾斜杠，消除对重定向的依赖。ES 影响面同步澄清：唯一线上消费方助手 KB 检索已内置 PG 回退、采集写入在服务器本地不受影响，**ES 维持现状不迁移**（后续如需释放内存再评估降级 PG 全文检索，排开发计划之后）。同日复现闲置回收后首请求 502：平台 init 仅 1.3s 但应用启动 ~18s（PG 连接池 + 渠道 seeding + assistant checkpointer），窗口内请求被函数内 nginx 拒绝；保温后 `/`、`/docs`、`/health` 全部 200——**预置并发从建议升级为必配**（SCF 控制台设 1×2048MB 实例）

### 5.2 迁移要点

- Web 函数沿用 [06-deployment.md §1](../arch/06-deployment.md) 定义的一体镜像与规格；API 网关触发器方案作废（该产品 2025-06-30 停服），入口用函数默认域名 / 自定义域名
- **冷启动**：镜像函数初始化默认 90s，个人低频使用需预置并发（1-2 实例）保体验——这是本阶段主要成本项，也是"是否值得迁移"的核心权衡
- Caddy 保留为 COS/MinIO 兼容层撤除后的过渡入口或直接下线

### 5.3 迁移后验收

两道关卡通过并完成切换后，以 [06-deployment.md §4.3](../arch/06-deployment.md) 为基线回归：域名 `/health` 200、助手流式经函数 URL 稳定出 token、预置并发下首请求体验可接受。观察期内保留回退能力（入口切回轻量服务器），稳定后再下线旧链路。

## 6. Phase 4：EdgeOne（已取消，2026-09-01）

原设想（2026-08-30 评估）：SPA → EdgeOne Pages 免费静态托管（静态请求迁出 SCF、发版与 API 解耦），助手对话 → EdgeOne Agent Runtime 会话独占沙箱承载（摆脱 SCF 900s）。

**取消结论（2026-09-01 用户评估裁决）**：

1. **EdgeOne 平台不引入**：经用户独立评估，相对现状没有特别明显的优势；为静态拆分与对话沙箱引入腾讯云主控制台体系外的新平台（独立 token 生命周期、DNS 依赖、双控制台管理面）得不偿失。助手对话由 SCF 进程内承载，实测流式 25.4s / LLM 归因约 90s，对 900s 上限余量 10 倍+，长时沙箱方案失去前提
2. **代码零影响**：Phase 4a 适配代码（后端 CORS 白名单化、前端 VITE_API_ORIGIN 跨域基址、CI deploy-pages job）全程停留在未合并分支，随分支删除回滚，develop 与生产未接收过任何改动
3. **AGS 备忘**：曾调研腾讯云 AGS（Agent 沙箱服务，文档中心 product/1814）作为长时承载替代——其为 E2B 兼容代码沙箱（e2b-code-interpreter SDK、编排留在调用方进程、沙箱实例运行时长默认 5min 可改、工具/实例配额各 10 可提配），无法直接消除 900s 约束；随 900s 前提消失，一并不再跟进

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
| TCR 个人版 | — | 免费额度内 |

结论：目标架构总成本与现状基本持平略升，核心收益是**发布自动化、机器瘦身可扩展、文件存储转托管**，而非省钱。
