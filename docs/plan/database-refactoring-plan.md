# 数据库命名规范 Review 与重构计划

> 目标：统一全库表名与字段命名风格，消除歧义缩写，提升可维护性与扩展性。

## 1. 现状概览

当前数据库通过 `docker/database/init-scripts/01-schema.sql` 与 `docker/database/migrations/` 下的原始 SQL 管理演进，共约 30 张表，覆盖：

| 分类 | 当前表名 | 问题 |
|---|---|---|
| 基础标的 | `stock_basic` | 孤立无前缀 |
| 行情数据 | `kline_daily`、`kline_minute`、`auction_data`、`index_auction` | 同类表未统一前缀；未体现标的类型（个股/指数） |
| 资金流向 | `fund_flow`、`sector_fund_flow` | 同类表未统一前缀；未体现标的类型 |
| 市场情绪/统计 | `market_breadth`、`market_amount`、`limit_up_pool`、`dragon_list` | `market_` 与 `pool` 语义混用 |
| 财务报表 | `balance_sheet`、`income_statement`、`cash_flow_statement` | 同类表未统一前缀 |
| 产业链 | `industry_chain_node`、`industry_chain_edge`、`company_chain_mapping` | `company_chain_mapping` 未共享 `industry_chain_` 前缀 |
| 资讯 | `news_announcement` | 规范 |
| AI 分析 | `ai_analysis_result` | 规范 |
| 用户 | `users`、`user_watchlist` | `users` 为复数 |
| 采集调度 | `collector_task`、`collector_log`、`collector_channel_configs`、`collector_channel_data_types` | 表名为复数 |
| 配置 | `llm_configs` | 表名为复数 |
| 文件 | `file_metadata` | 规范 |
| IPO | `ipo_info` | 规范 |
| 基金持仓 | `fund_holdings` | 表名为复数 |
| 宏观指标 | `macro_indicator` | 规范 |

主要问题：

1. **分类前缀缺失**：行情、资金流、财务报表、股池等同类表没有统一前缀，新表加入时难以判断归属。
2. **标的类型未显式表达**：K 线、竞价、资金流目前主要面向个股，后续扩展板块、指数时易出现命名冲突或歧义。
3. **命名风格不统一**：表名单复数混用（`users` vs `stock_basic`），缩写尺度不一致（`cf_operations` vs `cash_equivalents`）。
4. **部分字段语义不清**：`industry_l1`、`limit_stat`、`stat_time`、`position`、`es_id` 等需要结合代码才能理解。
5. **主键策略不一致**：部分表使用自然复合主键（`kline_daily`），部分表使用自增 ID + 业务唯一键（`limit_up_pool`）。
6. **Schema 与 SQLAlchemy 模型存在漂移**：如 `sector_fund_flow` 在 SQL 中为 `UNIQUE`，在模型中三列均标记为 `primary_key=True`。

## 2. 命名规范目标

- **一目了然**：表名见名知意，字段名不用猜。
- **统一风格**：全库采用小写蛇形命名（`snake_case`），表名单数，字段名完整词组。
- **分类前缀**：同一业务分类的表使用统一前缀，便于检索与扩展。
- **标的类型显式化**：支持个股（`stock`）、板块（`sector`）、指数（`index`）的同类数据扩展。
- **便于维护**：减少缩写，避免一词多义；约束、索引命名规范化。
- **对齐行业最佳实践**：遵循 PostgreSQL 社区与 SQLAlchemy 常见约定。

## 3. 推荐命名规范

### 3.1 表名

- 使用**单数名词**，小写蛇形命名。
- **同一分类的表必须共享统一前缀**，前缀即业务领域缩写。
- 表名结构遵循：**`<分类前缀>_<数据类型>_<标的类型>[_<粒度/子类型>]`**
  - 无标的类型的市场级数据可省略 `<标的类型>`。
  - 粒度/子类型按需出现，如 `_daily`、`_minute`。

#### 3.1.1 分类前缀总览

| 分类 | 前缀 | 说明 |
|---|---|---|
| 行情数据 | `quote_` | K 线、竞价等价格相关时序数据 |
| 资金流向 | `capital_` | 个股/板块/指数资金净流入 |
| 市场情绪/统计 | `market_` | 涨跌家数、成交额等市场级指标 |
| 股池 | `pool_` | 涨停池、龙虎榜等每日股票集合 |
| 财务报表 | `financial_` | 资产负债表、利润表、现金流量表 |
| 产业链 | `industry_chain_` | 产业链节点、边、公司映射 |
| 成分/映射 | `mapping_` | 指数成分、板块成分、产业链公司映射 |
| 资讯 | `news_` | 新闻、公告 |
| AI 分析 | `ai_` | AI 分析结果 |
| 采集调度 | `collector_` | 采集任务、日志、渠道配置 |
| 用户 | `user_` | 用户、自选股 |
| 基础标的 | `stock_` | 股票基础信息 |
| 文件 | `file_` | 文件元数据 |
| IPO | `ipo_` | 新股信息 |
| 基金持仓 | `fund_` | 基金持仓 |
| 宏观指标 | `macro_` | 宏观经济指标 |
| LLM 配置 | `llm_` | LLM 配置 |

#### 3.1.2 推荐表名映射

| 当前表名 | 推荐表名 | 说明 |
|---|---|---|
| `kline_daily` | `quote_kline_stock_daily` | 行情-K线-个股-日线；后续可自然扩展 `quote_kline_index_daily`、`quote_kline_sector_daily` |
| `kline_minute` | `quote_kline_stock_minute` | 行情-K线-个股-分钟线 |
| `auction_data` | `quote_auction_stock` | 行情-竞价-个股 |
| `index_auction` | `quote_auction_index` | 行情-竞价-指数 |
| `fund_flow` | `capital_fund_flow_stock` | 资金-流向-个股 |
| `sector_fund_flow` | `capital_fund_flow_sector` | 资金-流向-板块；后续可扩展 `capital_fund_flow_index` |
| `market_breadth` | `market_breadth` | 市场级指标，无标的类型 |
| `market_amount` | `market_amount` | 市场级指标，无标的类型 |
| `limit_up_pool` | `pool_limit_up_stock` | 股池-涨停-个股 |
| `dragon_list` | `pool_dragon_tiger_stock` | 股池-龙虎榜-个股；后续可扩展 `pool_broken_limit_stock` |
| `balance_sheet` | `financial_balance_sheet` | 财务-资产负债表；默认定位于个股，如需板块聚合可扩展 `financial_sector_balance_sheet` |
| `income_statement` | `financial_income_statement` | 财务-利润表 |
| `cash_flow_statement` | `financial_cash_flow_statement` | 财务-现金流量表 |
| `company_chain_mapping` | `industry_chain_company_mapping` | 共享产业链前缀；或改用 `mapping_industry_chain_company` |
| `users` | `user` | 统一单数 |
| `user_watchlist` | `user_watchlist` | 已规范，保留 |
| `llm_configs` | `llm_config` | 统一单数 |
| `collector_channel_configs` | `collector_channel_config` | 统一单数 |
| `collector_channel_data_types` | `collector_channel_data_type` | 统一单数 |
| `fund_holdings` | `fund_holding` | 统一单数 |
| `stock_basic` | `stock_basic` | 已规范，保留 |
| `news_announcement` | `news_announcement` | 已规范，保留 |
| `ai_analysis_result` | `ai_analysis_result` | 已规范，保留 |
| `collector_task` / `collector_log` | 保持不变 | 已规范 |
| `file_metadata` | 可保留 | `metadata` 为不可数名词 |
| `ipo_info` | 可保留 | 已规范 |
| `macro_indicator` | 可保留 | 已规范 |

#### 3.1.3 未来扩展示例

按 `<分类>_<数据类型>_<标的>` 模式，后续新增表可自然命名：

| 未来需求 | 推荐表名 | 说明 |
|---|---|---|
| 板块 K 线 | `quote_kline_sector_daily` | 与 `quote_kline_stock_daily` 同构 |
| 指数 K 线 | `quote_kline_index_daily` | 与个股 K 线区分 |
| 指数资金流 | `capital_fund_flow_index` | 与个股/板块资金流区分 |
| 指数成分股 | `mapping_index_stock` | 统一映射类前缀 |
| 板块成分股 | `mapping_sector_stock` | 统一映射类前缀 |
| 炸板池 | `pool_broken_limit_stock` | 与涨停池同前缀 |
| 跌停池 | `pool_limit_down_stock` | 与涨停池同前缀 |
| 板块财务聚合 | `financial_sector_balance_sheet` | 与个股报表区分 |

### 3.2 字段名

- 完整单词优先，行业通用缩写可保留（如 `eps`、`pe_ratio`）。
- 避免无上下文缩写：`l1` → `level_1`，`stat` → `status`。
- 同一语义使用同一单词：涨跌幅统一用 `change_pct`，不用 `pct_change` 与 `change_pct` 混用。

| 当前字段 | 推荐字段 | 说明 |
|---|---|---|
| `industry_l1` / `l2` / `l3` | `industry_level_1` / `level_2` / `level_3` | 层级含义清晰 |
| `pct_change` | `change_pct` | 与 `pool_limit_up_stock.change_pct` 等统一 |
| `cf_operations` | `cash_flow_from_operations` | 不用缩写 |
| `cf_investing` | `cash_flow_from_investing` | 同上 |
| `cf_financing` | `cash_flow_from_financing` | 同上 |
| `rd_expense` | `research_development_expense` | 或 `r_and_d_expense` |
| `es_id` | `elasticsearch_doc_id` | 明确 Elasticsearch 文档 ID |
| `limit_stat` | `limit_status` | 完整单词 |
| `stat_time` | `snapshot_time` | 避免与统计（statistic）混淆 |
| `broken_count` | `broken_limit_count` | 明确炸板计数 |
| `position`（产业链映射） | `chain_position` | 避免与持仓等语义冲突 |
| `source`（产业链边表） | `data_source` | 与图方向的 `source_node_id` 区分 |
| `uploaded_at`（文件表） | `created_at` | 统一审计字段命名 |

### 3.3 约束与索引命名

| 对象 | 推荐命名 | 示例 |
|---|---|---|
| 主键约束 | `pk_<table>` | `pk_stock_basic` |
| 唯一约束 | `uq_<table>_<columns>` | `uq_stock_basic_code_market` |
| 外键约束 | `fk_<table>_<ref_table>` | `fk_collector_log_collector_task` |
| 普通索引 | `idx_<table>_<columns>` | `idx_quote_kline_stock_daily_code_date` |
| 唯一索引 | `ux_<table>_<columns>` 或统一 `idx_` | 建议统一为 `idx_` 并标注 `UNIQUE` |
| CHECK 约束 | `chk_<table>_<column>` | `chk_stock_basic_market` |

当前 `collector_channel_data_type` 的约束/索引缩写 `ccdt` 建议改为完整前缀。

### 3.4 审计字段

所有业务表统一使用：

- `created_at TIMESTAMPTZ DEFAULT NOW()`
- `updated_at TIMESTAMPTZ DEFAULT NOW()`（如表会被更新）

当前 `file_metadata` 使用 `uploaded_at`、`company_chain_mapping` 仅有 `updated_at`，建议统一。

## 4. 发现的问题清单

按优先级分为高、中、低三档。

### 4.1 高优先级（影响正确性或开发效率）

| # | 问题 | 影响 | 建议处理 |
|---|---|---|---|
| 1 | `sector_fund_flow` Schema 与模型主键不一致：SQL 为 `UNIQUE`，模型三列均 `primary_key=True` | `create_all()` 生成的 DDL 与迁移 SQL 不一致 | 统一为 `PRIMARY KEY` 或统一为 `UNIQUE`；推荐复合主键 |
| 2 | `collector_log` 模型缺少 `task_id` 外键，且 `metadata` 字段映射为 `meta` | 无法通过 ORM 关联任务，字段名易混淆 | 补全 `task_id` 并统一属性名为 `metadata` |
| 3 | `auction_data.match_time` SQL 为 `TIME`，模型为 `DateTime` | 类型漂移 | 对齐类型 |
| 4 | 部分模型缺少 `created_at` 字段声明：`KlineDaily`、`KlineMinute`、`FundFlow`、`AuctionData` | ORM 查询/插入时无法访问审计字段 | 补齐模型字段 |
| 5 | `users.settings` 模型无默认值，Schema 为 `JSONB DEFAULT '{}'::jsonb` | 可能插入 `NULL` 导致下游处理不一致 | 模型声明默认值 `{}` 并 `nullable=False` |
| 6 | 6 张表无 SQLAlchemy 模型：`industry_chain_node`、`industry_chain_edge`、`company_chain_mapping`、`ai_analysis_result`、`dragon_list`、`macro_indicator` | 无法通过 ORM 维护，增加维护成本 | 评估是否补充模型；若仅由采集器写入，可保留但需文档化 |

### 4.2 中优先级（影响可读性与一致性）

| # | 问题 | 建议 |
|---|---|---|
| 7 | 同类表缺少统一分类前缀：行情、资金流、财务、股池 | 按第 3.1 节增加前缀 |
| 8 | 标的类型未显式表达，不便于扩展板块/指数同类数据 | 采用 `<分类>_<数据类型>_<标的>` 模式 |
| 9 | 涨跌幅字段命名混用：`pct_change` vs `change_pct` | 统一为 `change_pct` |
| 10 | 多个表名单复数混用 | 统一单数 |
| 11 | 行业层级字段缩写 `industry_l1/l2/l3` | 改为 `industry_level_1/2/3` |
| 12 | 现金流量表字段 `cf_*` 缩写 | 改为完整 `cash_flow_from_*` |
| 13 | `limit_stat`、`stat_time`、`broken_count` 语义不清 | 改为 `limit_status`、`snapshot_time`、`broken_limit_count` |
| 14 | `company_chain_mapping.position` 过于通用 | 改为 `chain_position` |
| 15 | `industry_chain_edge.source` 与 `source_node_id` 一词多义 | 数据出处改为 `data_source` |
| 16 | 主键策略不一致：复合自然键 vs 自增 ID + 业务唯一键 | 制定统一策略（见第 5 节） |
| 17 | `file_metadata.uploaded_at` 与审计字段命名不一致 | 改为 `created_at` |
| 18 | `llm_configs` 唯一索引前缀 `ux_` 与其他 `idx_` 不一致 | 统一为 `idx_` 或明确区分 `ux_` 仅用于唯一索引 |

### 4.3 低优先级（建议逐步优化）

| # | 问题 | 建议 |
|---|---|---|
| 19 | `ai_analysis_result` 同时存在 `id` 与 `analysis_id` | 保留一个即可，推荐以 `analysis_id` 为业务主键 |
| 20 | `dragon_list` 表名非中文用户不易理解 | 改为 `pool_dragon_tiger_stock` |
| 21 | 约束名 `uq_ccdt_channel_type` 使用缩写 | 改为 `uq_collector_channel_data_type_channel_data_type` |
| 22 | 部分模型未声明 CHECK 约束与部分索引 | 同步声明或移除 Schema 中未使用的索引 |

## 5. 重构方案

### 5.1 主键策略统一

推荐以下规则：

1. **时序/快照类数据**（每日/每分钟一条，天然由业务字段唯一）：使用复合自然主键。
   - 例：`quote_kline_stock_daily (stock_code, trade_date)`、`capital_fund_flow_stock (stock_code, trade_date)`、`capital_fund_flow_sector (sector_code, sector_type, trade_date)`。
2. **实体类数据**（股票、用户、任务、配置）：使用自增 `BIGSERIAL` 代理主键，业务唯一键加 `UNIQUE` 约束。
   - 例：`stock_basic`、`user`、`collector_task`。
3. **事件/日志类数据**（采集日志、AI 分析结果）：使用自增 `BIGSERIAL` 或 UUID，视查询需求而定。
   - 例：`collector_log`、`ai_analysis_result`。

按此规则，`pool_limit_up_stock`、`market_breadth`、`market_amount`、`quote_auction_index`、`ipo_info`、`fund_holding`、`pool_dragon_tiger_stock`、`macro_indicator` 等业务上“每日一条”的表，**可考虑**改为复合自然主键，减少冗余 `id` 列。但若已有大量查询依赖 `id`，可保留现状，仅统一命名。

### 5.2 分阶段重构计划

#### 阶段一：零停机重命名（低风险，优先做）

使用 PostgreSQL `ALTER TABLE ... RENAME COLUMN` 与视图兼容：

1. **表名增加分类前缀并统一单数**：
   - `kline_daily` → `quote_kline_stock_daily`
   - `kline_minute` → `quote_kline_stock_minute`
   - `auction_data` → `quote_auction_stock`
   - `index_auction` → `quote_auction_index`
   - `fund_flow` → `capital_fund_flow_stock`
   - `sector_fund_flow` → `capital_fund_flow_sector`
   - `limit_up_pool` → `pool_limit_up_stock`
   - `dragon_list` → `pool_dragon_tiger_stock`
   - `balance_sheet` → `financial_balance_sheet`
   - `income_statement` → `financial_income_statement`
   - `cash_flow_statement` → `financial_cash_flow_statement`
   - `company_chain_mapping` → `industry_chain_company_mapping`
   - `users` → `user`
   - `llm_configs` → `llm_config`
   - `collector_channel_configs` → `collector_channel_config`
   - `collector_channel_data_types` → `collector_channel_data_type`
   - `fund_holdings` → `fund_holding`
2. 对业务查询影响小的字段重命名：
   - `industry_l1/l2/l3` → `industry_level_1/2/3`
   - `pct_change` → `change_pct`
   - `cf_*` → `cash_flow_from_*`
   - `rd_expense` → `research_development_expense`
   - `es_id` → `elasticsearch_doc_id`
   - `limit_stat` → `limit_status`
   - `stat_time` → `snapshot_time`
   - `broken_count` → `broken_limit_count`
   - `position`（产业链映射） → `chain_position`
   - `source`（产业链边表） → `data_source`
   - `uploaded_at` → `created_at`
3. 重命名约束与索引：
   - `uq_ccdt_channel_type` → `uq_collector_channel_data_type_channel_data_type`
   - `ux_llm_configs_default` → `idx_llm_config_default`（表名单数后同步调整）

#### 阶段二：Schema-ORM 对齐

1. 补齐缺失模型与字段：
   - 为 `industry_chain_node`、`industry_chain_edge`、`industry_chain_company_mapping`、`ai_analysis_result`、`pool_dragon_tiger_stock`、`macro_indicator` 创建 SQLAlchemy 模型。
   - 在 `QuoteKlineStockDaily`、`QuoteKlineStockMinute`、`CapitalFundFlowStock`、`QuoteAuctionStock` 模型中补齐 `created_at`。
   - 在 `NewsAnnouncement` 模型中补齐 `keywords`。
2. 修复漂移：
   - `quote_auction_stock.match_time` 类型对齐。
   - `capital_fund_flow_sector` 主键/唯一约束对齐。
   - `collector_log` 补全 `task_id` 并将模型属性 `meta` 改为 `metadata`。
   - `user.settings` 模型声明默认值。
3. 在模型中补全 CHECK 约束与部分索引声明（或从 Schema 中移除未使用的）。

#### 阶段三：引入 Alembic 管理迁移

当前使用原始 SQL 文件管理迁移，随着表增多，难以检测模型与 Schema 的漂移。建议：

1. 初始化 Alembic：`alembic init alembic`。
2. 以当前 Schema 为 baseline 生成首个 revision。
3. 后续所有 DDL 变更通过 `alembic revision --autogenerate` + 人工审核生成。
4. 将 `docker/database/migrations/` 中已执行的 SQL 归档为历史脚本，新变更走 Alembic。

#### 阶段四：主键策略归一化（可选，风险较高）

对每日一条的表评估是否移除冗余 `id` 列，改为复合自然主键。此操作会改变主键类型，需同步调整：

- SQLAlchemy 模型
- 所有外键引用
- 依赖 `id` 的批量导入逻辑
- 测试数据构造

建议仅在表数据量不大、且无外部系统依赖时执行。

## 6. 迁移实施 checklist

- [ ] 备份生产数据库。
- [ ] 在本地/测试环境执行所有 `ALTER TABLE`/`RENAME`。
- [ ] 运行后端单元测试与集成测试，确认 SQLAlchemy 模型与查询正常。
- [ ] 运行采集器冒烟测试，确认写入路径正常。
- [ ] 更新 `backend/app/models/` 中所有相关模型。
- [ ] 更新所有引用旧字段/表名的 repository、service、spider 代码。
- [ ] 更新 `docker/database/init-scripts/01-schema.sql` 与迁移文件。
- [ ] 更新 API schema / Pydantic models（若字段名暴露到接口）。
- [ ] 更新前端类型与接口调用（若字段名已暴露）。
- [ ] 更新文档与数据字典。
- [ ] 引入 Alembic 并生成 baseline revision。

## 7. 验证方案

1. **命名规范扫描脚本**：编写 CI 脚本检查新增表/字段是否符合：
   - 小写蛇形命名
   - 无歧义缩写
   - 单数表名
   - 符合预定义的分类前缀白名单
   - 符合 `<分类>_<数据类型>_<标的>[_粒度]` 模式
2. **Schema-ORM 一致性检查**：使用 `sqlacodegen` 或 Alembic `autogenerate` 定期比对，输出漂移报告。
3. **代码审查清单**：PR 中新增数据库变更时，强制检查模型、迁移、索引、约束是否同步更新。

## 8. 附录：推荐命名对照表

### 8.1 表名对照

| 分类 | 当前表名 | 推荐表名 | 备注 |
|---|---|---|---|
| 行情-K线 | `kline_daily` | `quote_kline_stock_daily` | 增加 `quote_` 前缀并显式标的类型 |
| 行情-K线 | `kline_minute` | `quote_kline_stock_minute` | 同上 |
| 行情-竞价 | `auction_data` | `quote_auction_stock` | 明确个股竞价 |
| 行情-竞价 | `index_auction` | `quote_auction_index` | 明确指数竞价 |
| 资金-流向 | `fund_flow` | `capital_fund_flow_stock` | 增加 `capital_` 前缀并显式标的类型 |
| 资金-流向 | `sector_fund_flow` | `capital_fund_flow_sector` | 同上 |
| 市场-统计 | `market_breadth` | `market_breadth` | 已规范 |
| 市场-统计 | `market_amount` | `market_amount` | 已规范 |
| 股池 | `limit_up_pool` | `pool_limit_up_stock` | 统一 `pool_` 前缀并显式标的类型 |
| 股池 | `dragon_list` | `pool_dragon_tiger_stock` | 同上 |
| 财务 | `balance_sheet` | `financial_balance_sheet` | 统一 `financial_` 前缀 |
| 财务 | `income_statement` | `financial_income_statement` | 同上 |
| 财务 | `cash_flow_statement` | `financial_cash_flow_statement` | 同上 |
| 产业链 | `industry_chain_node` | `industry_chain_node` | 已规范 |
| 产业链 | `industry_chain_edge` | `industry_chain_edge` | 已规范 |
| 产业链 | `company_chain_mapping` | `industry_chain_company_mapping` | 共享 `industry_chain_` 前缀 |
| 用户 | `users` | `user` | 统一单数 |
| 用户 | `user_watchlist` | `user_watchlist` | 已规范 |
| 采集 | `collector_task` | `collector_task` | 已规范 |
| 采集 | `collector_log` | `collector_log` | 已规范 |
| 采集 | `collector_channel_configs` | `collector_channel_config` | 统一单数 |
| 采集 | `collector_channel_data_types` | `collector_channel_data_type` | 统一单数 |
| 配置 | `llm_configs` | `llm_config` | 统一单数 |
| 基金 | `fund_holdings` | `fund_holding` | 统一单数 |
| 基础标的 | `stock_basic` | `stock_basic` | 已规范 |
| 资讯 | `news_announcement` | `news_announcement` | 已规范 |
| AI | `ai_analysis_result` | `ai_analysis_result` | 已规范 |
| 文件 | `file_metadata` | `file_metadata` | 可保留 |
| IPO | `ipo_info` | `ipo_info` | 已规范 |
| 宏观 | `macro_indicator` | `macro_indicator` | 已规范 |

### 8.2 未来扩展表名示例

| 未来需求 | 推荐表名 | 说明 |
|---|---|---|
| 板块日 K 线 | `quote_kline_sector_daily` | 与个股 K 线同构 |
| 指数日 K 线 | `quote_kline_index_daily` | 与个股 K 线区分 |
| 指数资金流 | `capital_fund_flow_index` | 与个股/板块资金流区分 |
| 指数成分股 | `mapping_index_stock` | 统一映射类前缀 |
| 板块成分股 | `mapping_sector_stock` | 统一映射类前缀 |
| 炸板池 | `pool_broken_limit_stock` | 与涨停池同前缀 |
| 跌停池 | `pool_limit_down_stock` | 与涨停池同前缀 |
| 板块财务聚合 | `financial_sector_balance_sheet` | 与个股报表区分 |

### 8.3 字段名对照

| 领域 | 当前 | 推荐 | 备注 |
|---|---|---|---|
| 行业一级 | `industry_l1` | `industry_level_1` | 完整 |
| 行业二级 | `industry_l2` | `industry_level_2` | 完整 |
| 行业三级 | `industry_l3` | `industry_level_3` | 完整 |
| 涨跌幅 | `pct_change` | `change_pct` | 统一 |
| 经营现金流 | `cf_operations` | `cash_flow_from_operations` | 完整 |
| 投资现金流 | `cf_investing` | `cash_flow_from_investing` | 完整 |
| 筹资现金流 | `cf_financing` | `cash_flow_from_financing` | 完整 |
| 研发费用 | `rd_expense` | `research_development_expense` | 完整 |
| ES 文档 ID | `es_id` | `elasticsearch_doc_id` | 完整 |
| 涨停状态 | `limit_stat` | `limit_status` | 完整 |
| 统计时间 | `stat_time` | `snapshot_time` | 避免歧义 |
| 炸板数 | `broken_count` | `broken_limit_count` | 完整 |
| 产业链位置 | `position` | `chain_position` | 避免歧义 |
| 数据来源 | `source`（产业链边表） | `data_source` | 避免与 source_node 混淆 |
| 文件上传时间 | `uploaded_at` | `created_at` | 统一审计字段 |

---

*本计划建议按阶段逐步实施，优先完成阶段一与阶段二，可显著改善可读性并消除 Schema-ORM 漂移。*
