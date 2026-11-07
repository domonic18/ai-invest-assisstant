# CI/CD 流水线方案（2026-11-07）

> 落地文档：发布 / 回滚 / 排障见 [`docs/deployment-runbook.md`](../deployment-runbook.md)。
> 本文只记录**方案与决策**，不重复运行手册内容。

## 1. 背景

发布原先靠人工 SSH 上服务器手敲命令，存在三类硬伤：

1. **发布不可复现**：生产机 `/opt/investment` 是 git clone，工作树有未提交改动，
   迁移文件靠手工拷贝——代码 / 配置 / 迁移三者不对齐，回滚难定位
2. **磁盘无治理**：全链路无 prune / 保留策略，镜像 tag 只增不减
3. **迁移无门禁**：CI 的 `db-migration-guard` 只验过**空库从零重放**，
   真实的「线上 schema → 新 schema」增量路径从未被自动验证；且该 job 不在
   任何 docker job 的 `needs` 里，迁移坏了也拦不住镜像构建

## 2. 目标

PR 合并 develop → 本机测试环境自动更新；合并 main → 生产环境审批后自动更新；
数据库迁移自动执行；镜像与备份文件自动治理。**在安全稳定的前提下提速。**

## 3. 目标拓扑

```
PR → backend + web + db-migration-guard + db-incremental-guard   （全绿才继续）
   → docker-web / docker-collector / docker-signer / docker-paper-trade（构建推 TCR）
   → deploy-staging    （自托管 runner = 本机测试环境，自动）
   → deploy-production （GitHub Environment `production` + 人工审批 + 串行）
```

两条部署 job 复用同一份 `scripts/deploy.sh`，仅 `--env` 不同。

## 4. 关键决策（用户拍板）

| 决策 | 选择 | 理由 |
|---|---|---|
| 生产发布闸门 | **GitHub Environment + required reviewers** | 仓库为 public，Free 计划可用；比「谁改 main 谁发布」可控 |
| 回滚 | **自动回滚镜像**（部署失败自动退到 `previous_tag`） | 故障窗口最短；人工回滚在半夜不可靠 |
| 部署逻辑落点 | **收敛到服务器上一份可评审脚本，CI 经 SSH 调用** | public 仓库 + 生产执行仓库代码 = 生产 RCE 通道，不可接受 |
| 发布前数据库备份 | **暂不做** | 用户决策。缓解靠：每迁移单事务回滚 + expand-contract + 幂等静态检查。后续批次把 PG 备份从「后置池」提到「发布前置」 |

补充设计判断：**停推 `latest`**。它是回滚可靠性的前提——TCR 对同 digest 的 tag 会连坐删除，
`latest` 会被回滚目标顶掉。tag 改为不可变的 `<branch>-<sha_short>`。

## 5. 关键机制

- **单一部署入口** `scripts/deploy.sh`：参数校验 → 预检 → `.env` 备份轮转 + 钉 `APP_TAG` →
  数据库迁移（先行）→ 换容器 → 健康检查 → 落 `.deploy-state` → 失败自动回滚 → 镜像/备份清理
- **迁移先行**：迁移失败即中止，旧版本继续服务；迁移 forward-only，回滚镜像不回滚 schema
- **并发互斥**：迁移全程单 psql 会话 + 会话级 advisory lock，并发部署排队而非同时改 schema
- **镜像治理**：每仓库保留最新 3 个 tag（当前 + 2 个回滚目标），只跑 `docker image prune -f`，
  **绝不 `-a`**（会把回滚目标删掉）
- **CI 门禁**：
  - `db-migration-guard`：空库从零重放 + 幂等重放断言
  - `db-incremental-guard`（新增）：从 `origin/main` 的 schema 出发走增量路径，
    再断言增量结果的列/索引/约束清单与从零重放**完全一致**（无 schema 漂移）
  - `scripts/check_migration_idempotency.py`（新增）：逐条语句静态扫描，
    拦下 `CREATE TABLE` / `ADD COLUMN` / `CREATE INDEX` 缺 `IF NOT EXISTS`、
    `INSERT` 缺 `ON CONFLICT` 的写法（历史文件进豁免名单，forward-only 不可回改）
  - 四个 docker job 的 `needs` 补齐上述守卫——迁移坏了不许出镜像
- **镜像 tag 全链一致**：构建与部署两端都用 `git rev-parse --short=7 "$GITHUB_SHA"`
  算 tag（显式钉长度，不用自动缩写——自动长度随对象库大小漂移，构建机与生产机
  可能算出不同长度）。tag 形如 `main-1a2b3c4`，与 `deploy.sh` 的校验正则一致
- **服务器 git 拉取**：**不走这条路**。实测生产机到 `github.com` **100% 不可达**
  （`git ls-remote` 8/8、`git fetch` 4/4 全部 60s 超时；裸 HTTPS `curl https://github.com/`
  25s 超时，而 `codeload.github.com` 1.02s、`ccr.ccs.tencentyun.com` 0.09s——是 host 级不可达，
  不是间歇性抖动），放在发布关键路径上等于每次发布都赌一次超时。
  改为 **CI 侧打包直传**：`scripts/deploy.sh` + `docker/database/` + `docker/caddy/` +
  `docker-compose.prod.yml` 经 SSH 送到服务器，与 `git checkout` 到同一 commit 等价；
  本次发布的完整 sha 由 CI 写入 `.deploy-commit`，`.deploy-state.commit` 从它取值，
  部署脚本不再依赖服务器上存在 git 仓库。
  镜像链路（构建 → TCR → 生产 pull）**全程境内且稳定**（生产 pull 0.74s），
  未作任何改动——直传只补源码/配置这条断掉的链路

## 6. 实施批次

| 批次 | 内容 | 状态 |
|---|---|---|
| 1 · 本机测试链路 | `scripts/deploy.sh`（staging 模式）+ `docker-compose.ci.yml` + `deploy-staging` job + celery-beat healthcheck | ✅ 已落地并本地全流程演练通过 |
| 2 · 生产链路 | Environment + required reviewers + `DEPLOY_SSH_KEY` / `DEPLOY_KNOWN_HOSTS` + 服务器侧 TCR 凭据 + `deploy-production` job | ✅ 工作流已落地，**待配置 secret 与 Environment 后首次手动触发** |
| 3 · 门禁与治理 | `needs` 补齐 + `db-incremental-guard` + advisory lock + 幂等静态检查 + 三层清理策略 | ✅ 已落地 |
| 4 · 文档 | runbook + README + `.env.example` + CLAUDE.md 发布纪律 | ✅ 已落地 |

## 7. 验证结果

- **本机全流程演练**（staging）：预检 → 迁移（`applied=0, skipped=25`）→ 拉镜像（本地回退）→
  11 个容器全部 healthy（含新增 celery-beat healthcheck）→ `.deploy-state` 落 `status=OK` →
  `.env.bak` 轮转 → 镜像清理 → 退出码 0。bash 5.3 与 macOS 系统 bash 3.2 各跑通一遍
- **回滚演练**：故意用「一启动即退出」的 web 镜像发布 → 换容器失败 →
  自动回滚到上一个 tag 并全部恢复 healthy → `.deploy-state` 落 `status=ROLLED_BACK`，
  `.env` 的 `APP_TAG` 同步退回
- **迁移失败路径**：迁移失败 → 中止且不换容器 → `APP_TAG` 退回上一个版本
  （早期版本此处会留下脏 tag，导致下次回滚目标错位，已修）
- **迁移脚本**：新库应用 → 幂等重放（`applied=0`）→ 故障迁移（表已建但后续语句报错）
  断言事务回滚、台账未污染、失败文件名可定位——三种路径均符合预期
- **增量守卫**：本地复刻 CI 的增量路径（origin/main 的 schema → 增量 → 与从零重放比对）——
  列 1087 / 索引 288 / 约束 301 三张清单完全一致；人为加一列后能检出漂移
- **幂等静态检查**：注入违规迁移文件 → 检查红并精确报出文件与语句；移除后绿
- **静态检查**：`shellcheck -S warning`（两个脚本）干净、`actionlint` 干净、
  `docker compose config` 合并通过

## 8. 明确不做 / 已接受风险

- **不做 GitOps**（ArgoCD / Flux）：单机单 compose 的场景收益低于引入复杂度
- **不在生产机放 runner**：public 仓库 + 生产执行仓库代码 = 直接 RCE 通道
- **CI 内联 ssh 长命令**：不可评审、难回溯，部署逻辑收敛到服务器端一份脚本
- **不做发布前数据库备份**（用户决策）
- **不改生产 redis 鉴权 / 5432 暴露**：独立加固项，本次不动

## 9. 首次生产发布前必须确认

1. **服务器工作树**：CI 已改为直传资产，不再 `git checkout --force` 也不再 `git clean`，
   服务器工作树原样保留、只被同名文件覆盖
   - **已核实（2026-11-07）**：服务器工作树虽脏，但内容与 `origin/main` **逐字节一致**
     （`docker-compose.prod.yml` blob `5aaaf8ce`、`docker/caddy/Caddyfile` blob `bd97e7e4`、
     12 个未跟踪迁移文件 blob 与 main 一致），直传覆盖后线上生效内容与 main 一致
   - 服务器克隆的 refspec 已放宽为 `+refs/heads/*:refs/remotes/origin/*`，
     但发布链路已不依赖它（GitHub 链路不稳）
2. GitHub secret `DEPLOY_SSH_KEY` / `DEPLOY_KNOWN_HOSTS`
   - **已配置（2026-11-07）**：专用 ed25519 密钥对，公钥已装进服务器 `authorized_keys`
     （原 1 条 + 新 1 条）；`known_hosts` 三种密钥类型指纹与服务器 host key 逐一比对一致
3. GitHub Environment `production` 的 required reviewers —— **用户已配置**
4. 生产机 `/root/.docker/config.json` 已有 TCR 凭据（600）
   - **已核实**：文件存在（600），auths 含 `ccr.ccs.tencentyun.com`，与 compose 镜像前缀一致
5. 直传机制已演练：`tar + scp + 解压` 在服务器 `/tmp` 沙箱验证，
   解压出的迁移集与线上现有迁移集 `diff` 完全一致，compose 文件一致，`deploy.sh` 语法通过

## 10. 首次生产发布实录（2026-11-07）

**第一次尝试（merge commit `189f906`）失败在「同步资产」步骤，部署步骤未执行，线上零影响。**

现象：`tar: docker/caddy/Caddyfile: Cannot open: File exists` /
`tar: docker/caddy/Dockerfile: Cannot open: Permission denied`。

根因：远端 `tar -xzf` 以 `ubuntu` 身份执行，而服务器 `/opt/investment/docker/caddy/`
是 **root 属主**（2026-10-16 手工发布时以 root 创建，此后未改属主）。
非 root 无法覆盖 root 属主目录里的文件 → tar 报错退出。
tar 会跳过错误继续解后面的条目，所以 `scripts/deploy.sh`、25 个迁移、compose 事实上已落地，
但 `.deploy-commit` 因 `set -eu` 未写入——**同步是「半套」状态**。

修法（三处）：
1. 远端提取整体改走 `sudo bash -s`（发布本来就要 root 权限执行 deploy.sh）
2. `tar --no-same-owner`：不让归档里的构建机 uid 覆盖服务器属主
   （否则文件会挂上构建机的 uid 501，服务器上不存在该用户）
3. 同步步骤加**资产落地完整性校验**：关键文件缺一即中止，迁移文件数与 CI 侧
   不一致也中止——不让半套资产带着进下一步

验证：修复方案在服务器实测通过（`--- 已同步：迁移 25 个，发布资产齐全 ---`）。
失败后的线上状态已核对：`APP_TAG` 仍为 `main-67efbb7`，11 个容器全部 running。
