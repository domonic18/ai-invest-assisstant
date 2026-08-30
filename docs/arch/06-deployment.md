# 部署架构与运维

> 目标架构设计（最终形态）。实施路线与现状问题分析见 [../plan/deployment-evolution-plan.md](../plan/deployment-evolution-plan.md)；部署全景图见 [00-overview.md §2](./00-overview.md)。

## 1. 节点与职责

| 节点 | 承载内容 | 技术形态 |
|------|----------|----------|
| EdgeOne Pages | React SPA 静态托管（免费静态托管档），**SPA 公网唯一出口**；域名 `invest.17aitech.com`（已备案） | 静态资源，`VITE_APP_VERSION` 由 CI 注入 |
| EdgeOne Agent Runtime | deepagents 助手对话运行时**主承载**（会话独占沙箱，毫秒级冷启动）；不受 SCF 900s 限制（边缘档单次执行上限 3600s） | 回调核心 API，不直连数据库 |
| SCF Web 函数 | FastAPI API 层（`docker/web` 一体镜像：nginx + uvicorn），SSE 流式输出；仅承载 `/api/*`，静态请求不经此出口 | 内存 2048MB，超时 900s，预置并发 1-2 实例保冷启动；镜像内 nginx 静态兜底仅服务本地 compose / 灾备 |
| 轻量应用服务器 2C4G（ap-beijing） | 数据层（postgres/timescale、redis、elasticsearch）+ 任务层（celery-beat + worker〔realtime+batch〕+ worker-heavy〔并发=1〕） | Docker Compose 编排；采集爬虫与 LLM 归因永久驻留 |
| COS | 研报/财报 PDF、知识库文件（S3 兼容端点）；`pg_dump` 定时备份目标 | 应用经 S3 SDK 读写 |
| TCR（ccr.ccs.tencentyun.com/domonic18） | 镜像仓库：`web-api` + `collector` 双镜像，linux/amd64 | tag = `latest` + git short sha |

**采集任务留置轻量服务器的三条理由**（不随 API 迁 SCF）：

1. **900 秒硬上限**：SCF 最大执行时长 900s，概念成分采集实测约 22 分钟，超限且不宜拆分（全有或全无语义）
2. **WAF 出口稳定性**：东财 WAF 按 TLS 指纹 + 主机限流，SCF 共享出口 IP 池风险高于轻量服务器固定出口 IP
3. PG/Redis 驻留轻量，worker 与数据同机时延最低

**助手对话不受 900s 约束**：900s 是 SCF 函数执行上限；助手对话由 EdgeOne Agent Runtime 会话沙箱承载后不再经过函数时长闸门。边缘档单次执行上限 3600s、会话空闲 300s，对话分钟级场景余量充足，配额形式为沙箱数量 + 沙箱回收时间（可提工单调整）。若未来出现 >1h 的长时 Agent（如深度研报告成），升级路径为腾讯云 Agent Runtime（云端独立产品，会话持续运行最长 7 天、暂停保留 30 天且暂停期间不收费）。任务侧（worker 拓扑）收缩为双 worker：realtime 与 batch 合并（时间窗天然错开：batch 定点盘后、realtime 盘中），heavy 独立容器且并发=1——LLM 分钟级任务不得占用通用采集池。

## 2. 网络与域名

- **公网入口**：`invest.17aitech.com`（已备案）→ EdgeOne 接入；SPA 静态资源走 Pages，`/api/*` 走 SCF（自定义域名或函数默认域名），助手对话经 Agent Runtime 会话沙箱承载（沙箱内回调 SCF API 取数）
- **内网互通**：SCF 绑定 VPC，经**云联网 CCN** 连接轻量服务器 VPC（同地域免费），读写 PG/Redis/ES
- **文件访问**：COS 预签名 URL 下发下载，前端不直连存储
- **备份链路**：轻量服务器 `pg_dump` 定时任务直推 COS

## 3. 镜像与发布

- **web-api 镜像**（`docker/web/Dockerfile`）：前端 vite 构建注入 `VITE_APP_VERSION`，nginx + FastAPI 合一，:9000 端口；SPA 公网出口走 EdgeOne Pages，镜像内静态资源仅作兜底（本地 compose / 灾备）
- **collector 镜像**（`docker/collector/Dockerfile`）：`COLLECT_TASK` 单任务模式 / `COLLECTOR_MODE=beat|worker` 常驻模式
- **发布流**：push develop → GitHub Actions 构建推送 TCR → 轻量服务器 `.env` 以 `APP_TAG` 钉版（git 短 sha，缺省 latest）后 `docker compose pull && docker compose up -d`、SCF 更新镜像版本；服务器不执行任何构建（实施细节与应急构建见 [deployment-evolution-plan.md](../plan/deployment-evolution-plan.md)）

## 4. 运维实操

### 4.1 数据库迁移

本地库为 schema 真相源：变更落地为 `docker/database/migrations/*.sql`（幂等可重复执行），**同步更新 `01-schema.sql` 与 `03-seed.sql`**（历史上已四例漂移）。远程应用：

```bash
sudo docker exec -i investment-postgres-1 psql -U invest -d invest -v ON_ERROR_STOP=1 < <migration>.sql
```

注意远程凭据为 `invest/invest`（≠本地 `user/invest`）。

### 4.2 调度变更

`collector_task` 表为调度唯一真相源，beat 周期同步 DB，插行/改行即生效，无需重启。

### 4.3 验收清单

- web/API：`curl localhost:9000/health` 200；SPA `/` 200；域名 `https://invest.17aitech.com/health` 200
- worker：`docker exec investment-celery-worker-1 python -m celery -A collector.celery_app inspect ping`（heavy 同理换 `investment-celery-worker-heavy-1`）
- registry：`GET /api/v1/admin/collector/tasks/catalog` 任务数与注册表一致
- 助手：流式对话经 Agent Runtime 入口正常出 token、可中断
- 备份：COS 上存在当日 `pg_dump` 对象
