# 质量重构计划（2026-09 评审落地）

来源：2026-09-25 全仓质量评审（综合 74.4/100）。本计划收敛为 5 个批次，
按依赖顺序执行，每批次独立验证（typecheck + 单测 + 构建）后提交。

> **状态（2026-09-25）：B1–B5 全部完成。** 终验：backend ruff/mypy(467 files)/pytest -m unit(2342) 全绿；
> web typecheck/lint/build 全绿、vitest 414 全绿、npm audit 0 漏洞。health_judge.py 按计划保留为已知例外。

## 批次总览

| 批次 | 内容 | 主要产出 | 验证 |
|------|------|---------|------|
| B1 | README 重写对齐终态架构 | README.md（消除与 docs/arch 的 3 组矛盾） | 人工比对 arch 文档 |
| B2 | npm dev 工具链漏洞修复 | web/package.json 升级 vitest/vite 链 | npm audit 归零 + 单测全绿 |
| B3 | 文档 4 处小漂移修复 | 00-overview 子域清单 / model_config / PaperTrade / arch/12 引用 | grep 复查 |
| B4 | shared/types/api.ts 拆分 | 1246 行 → 按域拆入既有 17 域类型文件 | web typecheck + test:unit |
| B5 | 高复杂度子域重构 | trading/kb/social/market 高分支文件拆解 | mypy + pytest -m unit + 前端检查 |

## B1 README 重写

问题：README「架构概览/技术栈/项目结构」停留在早期方案，与终态架构直接矛盾。

- 采集架构：Scrapy + SCF Job → **自研 collector runtime + Celery 双 worker + 轻量服务器驻留**（00-overview §2）
- AI 框架：PydanticAI / OpenAI Agents SDK → **deepagents (LangChain/LangGraph) + YAML Skills**
- 删除不存在的 `miniapp/`（Taro 小程序）章节与能力矩阵中的小程序列、`Makefile` 引用（改为 compose/npm/uv 实际命令）
- 项目结构树对齐 00-overview §5（backend/collector、shared、docker 4 镜像、qa、skills）

## B2 npm dev 工具链漏洞

问题：npm audit 14 漏洞（critical 2 + high 6），全部位于 vitest/vite 构建测试链。

- `npm audit fix` 处理 semver 内可升项；vitest/vite 大版本升级单独评估（breaking 变更须过全量单测）
- 升级后 `npm audit` 归零为验收标准；生产依赖（react-router 等 runtime 链）不受影响

## B3 文档小漂移（4 处）

| 位置 | 修复 |
|------|------|
| 00-overview §3 / §5 services+repositories 注释 | 子域清单补 kb/quota/social/trading/common（实际 17） |
| 00-overview:130 admin 模块注释 | `llm_config` → `model_config`（PR #75 归并） |
| 00-overview §5 pages 清单 | 补 `PaperTrade/`（模拟盘页） |
| 04-ai-agent.md:326 | 悬空引用 `arch/12 §7` → `arch/09 §7`（KB 新编号） |

## B4 shared/types/api.ts 拆分

问题：api.ts 1,246 行为全仓唯一 >1000 行文件，全域 wire 类型聚合。

- 消费方全部经 `shared/types/index.ts` 桶导入（`export * from './api'`），拆分对消费方零感知
- 拆法：按域将 `Api*` 接口迁入既有域文件（user/stock/kline/auction/fund_flow/market/...），
  迁移完的段落从 api.ts 删除；无法归域的保留在 api.ts 并缩减其体积
- 红线：不改任何字段定义（wire 契约零变化），仅移动声明位置

## B5 高复杂度子域重构

问题：>20 分支文件 71 个，新增子域（trading/kb/social）与技术指标/健康判定是重灾区。

目标文件与拆法（先服务层、后前端，每文件拆后跑对应单测）：

| 文件 | 分支数 | 拆法 |
|------|--------|------|
| services/trading/paper_trade_service.py (771行/48) | 48 | 按三层拆：`paper_trade_mappers.py`（纯行转换 helper）+ `paper_trade_sync.py`（同步链路 upsert/sync_daily）+ 主文件保留交易操作（下单/撤单/查询） |
| services/market/index_technical_service.py (44) | 44 | 指标计算函数按指标族拆 `indicators_*.py` 纯函数模块 |
| services/kb/extract_service.py (43) | 43 | 抽取编排与 LLM 交互/状态推进分离 |
| services/common/minio_service.py (42) | 42 | 通用对象操作与业务封装（KB 素材/文件元数据）分离 |
| services/news/topic_service.py (37) | 37 | 聚类/快照落库/线Figures 查询分层 |
| spiders/eastmoney_financial_statement.py (43) | 43 | 解析函数下沉 collector.core.parsing 或模块内 parse_* 分离 |
| web/utils/cron.ts (42) | 42 | 解析/校验/格式化纯函数分组拆文件 |
| web/components/charts/drawing/useDrawingLayer.ts (54) | 54 | 事件处理/命中检测/重绘调度拆 hooks |

不动 health_judge.py（56）：规则引擎形态，分支数即业务规则数，拆分反降可读性——登记为已知例外。

验收：目标文件分支数降至 20 以下；mypy/pytest/web 检查全绿；行为零变化（无接口/表结构变更）。

## 完成定义

- 5 批次全部落地且验证绿
- `npm audit` 0 漏洞
- `shared/types/` 无 >1000 行文件；B5 目标文件圈复杂度 ≤20（health_judge 例外登记）
- README 与 docs/arch 无矛盾表述
