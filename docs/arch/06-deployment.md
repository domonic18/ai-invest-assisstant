# 部署架构与运维

> 目标架构设计（最终形态）。实施路线与现状问题分析见 [../plan/deployment-evolution-plan.md](../plan/deployment-evolution-plan.md)；部署全景图见 [00-overview.md §2](./00-overview.md)。

## 1. 节点与职责

| 节点 | 承载内容 | 技术形态 |
|------|----------|----------|
| SCF Web 函数 | web-api 一体镜像（`docker/web`：单 uvicorn 进程）：React SPA（FastAPI 静态托管）与 FastAPI API 层**同源同端口**（:9000），SSE 流式输出；助手对话（deepagents）进程内承载 | 内存 2048MB，超时 900s，预置并发 1-2 实例保冷启动；自定义域名 `invest.17aitech.com`（已备案） |
| 轻量应用服务器 2C4G（ap-beijing） | 数据层（postgres/timescale、redis、elasticsearch）+ 任务层（celery-beat + worker〔realtime+batch〕+ worker-heavy〔并发=1〕） | Docker Compose 编排；采集爬虫与 LLM 归因永久驻留 |
| COS | 研报/财报 PDF、知识库文件（S3 兼容端点）；`pg_dump` 定时备份目标 | 应用经 S3 SDK 读写 |
| TCR（ccr.ccs.tencentyun.com/domonic18） | 镜像仓库：`web-api` + `collector` 双镜像，linux/amd64 | tag = `latest` + git short sha |

**采集任务留置轻量服务器的三条理由**（不随 API 迁 SCF）：

1. **900 秒硬上限**：SCF 最大执行时长 900s，概念成分采集实测约 22 分钟，超限且不宜拆分（全有或全无语义）
2. **WAF 出口稳定性**：东财 WAF 按 TLS 指纹 + 主机限流，SCF 共享出口 IP 池风险高于轻量服务器固定出口 IP
3. PG/Redis 驻留轻量，worker 与数据同机时延最低

**助手对话随 API 同进程承载**（deepagents / LangGraph 运行于 web-api 内）：实测流式对话 25.4s、LLM 归因约 90s，对 900s 函数执行上限余量 10 倍以上；独立沙箱运行时（EdgeOne Agent Runtime 等）经评估不引入——拆分收益不抵新增平台的管理面与凭据/DNS 依赖。任务侧（worker 拓扑）为双 worker：realtime 与 batch 合并（时间窗天然错开：batch 定点盘后、realtime 盘中），heavy 独立容器且并发=1——LLM 分钟级任务不得占用通用采集池。

## 2. 网络与域名

- **公网入口**：`invest.17aitech.com`（已备案）→ SCF Web 函数自定义域名；SPA 与 `/api/*` 同源同端口（一体镜像 :9000），无跨域
- **数据面互通**：SCF 不绑 VPC（默认具备公网出口），经轻量服务器公网 IP 直连 PG/Redis——轻量防火墙放行 5432/6379，Redis requirepass / PG 账号密码认证；ES 无认证留置轻量本地、不对外发布
- **文件访问**：COS 预签名 URL 下发下载，前端不直连存储
- **备份链路**：轻量服务器 `pg_dump` 定时任务直推 COS

## 3. 镜像与发布

- **web-api 镜像**（`docker/web/Dockerfile`）：前端 vite 构建注入 `VITE_APP_VERSION`，单 uvicorn 进程直听 :9000（API + SPA 静态托管合一，`STATIC_DIR=/app/static`）；与 API 同源（SCF 与本地 compose 同一形态）
- **冷启动策略**：单进程消除"代理端口已开而后端未就绪"的 502 竞态；lifespan 预热（渠道 seeding / 助手 checkpointer）走后台任务不阻塞监听，`/health` 返回 `warmup_done` 观测位；前端对幂等 GET 在 502/503/504/网络错误时自动重试（1s/2s 退避）。SCF 控制台 env 须显式设 `FORCE_FORWARDED_HTTPS=1`（入口 HTTPS 但以 HTTP 转发容器且不带 `X-Forwarded-Proto`，中间件据此强制 scheme=https；本地 http 访问保持 0）
- **collector 镜像**（`docker/collector/Dockerfile`）：`COLLECT_TASK` 单任务模式 / `COLLECTOR_MODE=beat|worker` 常驻模式
- **发布流**：push develop → GitHub Actions 构建推送 TCR → 轻量服务器 `.env` 以 `APP_TAG` 钉版（`<分支>-<git 短 sha>`，如 `develop-4cdc1b7`，缺省 latest）后 `docker compose pull && docker compose up -d`、SCF 更新镜像版本；服务器不执行任何构建（实施细节与应急构建见 [deployment-evolution-plan.md](../plan/deployment-evolution-plan.md)）

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
- 助手：流式对话经函数 URL 入口正常出 token、可中断
- 备份：COS 上存在当日 `pg_dump` 对象
