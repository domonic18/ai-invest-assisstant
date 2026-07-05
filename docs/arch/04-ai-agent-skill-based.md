# AI Agent 体系设计（Skill 驱动版）

## 1. 核心理念转变

原始方案问题：LangGraph 需要写大量 Python 代码定义 Agent 逻辑、图结构。

Skill 驱动方案：将分析逻辑封装为 Codex Skill，每个 Skill 用自然语言描述分析步骤，
由 Codex CLI 的 Agent 引擎自动执行 —— **你不需要写代码，只需要写分析指令**。

```
传统方案：                    Skill 驱动方案：
写 Python 代码               写 Skill 描述文件 (SKILL.md)
→ 定义 Graph                   → 自然语言描述分析流程
→ 实现 Node                      → 声明需要的工具/数据源
→ 配置 Edge                      → 声明输入/输出格式
→ 部署服务                       → 放入 .codex/skills/ 即用
```

## 2. Skill 体系设计

### 2.1 Skill 目录结构

```
crawler/
└── .codex/
    └── skills/
        ├── industry-chain-analysis/    # 产业链分析 Skill
        │   └── SKILL.md
        ├── research-summary/           # 研报摘要 Skill  
        │   └── SKILL.md
        ├── hotspot-detection/          # 热点发现 Skill
        │   └── SKILL.md
        ├── financial-health-check/    # 财务体检 Skill
        │   └── SKILL.md
        └── chain-breakthrough/        # 产业链突破点 Skill
            └── SKILL.md
```

### 2.2 产业链分析 Skill 示例

这个是核心 Skill，对应你提到的"对某个行业进行上下游产业链分析"需求：

```markdown
# Industry Chain Analysis

## 描述
对指定行业进行上下游产业链分析，输出产业链图谱和分析报告。

## 触发条件
- 用户要求分析某行业产业链
- 用户询问某行业上下游关系
- 用户要求对比产业链不同环节

## 分析流程

### 步骤1：数据准备
1. 调用 akshare 获取行业内所有上市公司列表和行业分类
2. 从 PostgreSQL 查询这些公司的最近一期财务数据（毛利率、营收、净利润）
3. 从 Elasticsearch 搜索该行业近期新闻和公告
4. 从 Milvus 知识库检索与"{industry} 产业链 供应商 客户 上下游"相关的研报/财报片段

### 步骤2：产业链结构识别
1. 基于检索到的研报内容、公司业务描述，分析行业的上游、中游、下游构成
2. 对每个环节，识别 3-5 家代表性上市公司
3. 确定环节之间的供需关系、技术依赖关系

### 步骤3：财务对比分析
1. 对比各环节代表公司的毛利率、净利率变化趋势（近3年）
2. 计算各环节的平均营收增速和研发投入占比
3. 分析各环节的议价能力（应收账款周转率、预收账款占比）

### 步骤4：价值分布与瓶颈识别
1. 绘制产业链价值分布（各环节毛利率贡献对比）
2. 识别利润最集中的环节
3. 识别存在产能瓶颈或技术卡脖子的环节
4. 从新闻/公告中提取各环节最新的技术突破和产能扩张信号

### 步骤5：输出生成
1. 生成产业链节点 JSON（节点名称、类型、代表公司、平均毛利率、议价能力评分）
2. 生成产业链边 JSON（上下游关系、关系强度、关系描述）
3. 输出分析摘要（500字以内）
4. 输出投资机会列表（3-5个）
5. 输出风险提示列表（2-3个）

## 输出格式
```json
{
  "nodes": [
    {
      "name": "硅材料",
      "type": "upstream", 
      "companies": [{"code": "600703", "name": "三安光电"}],
      "avg_gross_margin": 25.3,
      "revenue_growth": 12.5,
      "bargaining_power": 7.5
    }
  ],
  "edges": [
    {
      "source": "硅材料",
      "target": "晶圆制造",
      "relation": "原材料供应",
      "strength": 85,
      "description": "高纯度硅片是晶圆制造的核心原材料"
    }
  ],
  "summary": "半导体产业链呈现...",
  "opportunities": ["..."],
  "risks": ["..."]
}
```

## 可用工具
- `python3` - 执行 akshare 数据获取脚本
- PostgreSQL 查询 (app/data/postgres)
- Milvus 向量检索 (app/data/milvus)  
- Elasticsearch 全文搜索 (app/data/elasticsearch)
- 文件读写（读写中间结果和最终输出）
```

### 2.3 研报摘要 Skill

```markdown
# Research Report Summary

## 描述
对指定公司或行业的券商研报进行批量摘要提取，输出结构化观点。

## 触发条件
- 用户要求查看某公司研报观点
- 用户要求对比多家券商对同一公司的看法
- 用户要求跟踪评级变化

## 分析流程

### 步骤1：研报检索
1. 从 PostgreSQL 查询目标公司最近的研报元数据
2. 从 MinIO 获取研报 PDF 文件路径
3. 从 Milvus 知识库检索研报文本切片（优先检索"投资建议""盈利预测""风险提示"段落）

### 步骤2：多券商观点提取
1. 对每篇研报，提取以下关键信息：
   - 评级（买入/增持/中性/减持/卖出）
   - 目标价
   - 核心逻辑（3句话以内）
   - 盈利预测（未来2年营收/净利润预测）
   - 风险提示
2. 按券商分组，展示各券商观点

### 步骤3：评级变化检测
1. 对比该券商上一次对同一公司的评级
2. 标注评级变化方向（上调/维持/下调）
3. 标注目标价变化幅度

### 步骤4：共识与分歧
1. 计算券商评级一致度（买入占比、中性占比、卖出占比）
2. 计算目标价区间（最低-最高）
3. 识别存在显著分歧的观点（同一指标预测差异>30%）

### 步骤5：输出
输出研报分析报告，包含：
- 评级分布图数据
- 目标价区间
- 核心看多逻辑汇总
- 核心看空逻辑汇总
- 最值得关注的3篇研报摘要
```

### 2.4 热点发现 Skill

```markdown
# Hotspot Detection

## 描述
实时追踪市场热点，发现产业链突破点和资金异动。

## 触发条件
- 用户要求查看当日/近期热点
- 用户询问某行业最新动态
- 用户要求发现投资机会

## 分析流程

### 步骤1：新闻聚合
1. 从 Elasticsearch 查询最近24小时的财经新闻
2. 按行业/主题进行聚类（利用新闻标签和关键词）
3. 计算每个主题的新闻数量和热度指数

### 步骤2：情绪分析
1. 对每个热点主题的新闻进行情绪分析
2. 标记积极/消极/中性
3. 计算情绪强度分数

### 步骤3：资金流向交叉验证
1. 从 PostgreSQL 查询当日的板块资金流向
2. 与热点主题进行匹配
3. 标记"资金+情绪共振"的板块

### 步骤4：产业链突破点
1. 对热点主题中涉及"技术突破""产能扩张""新产品""政策支持"的新闻进行深度提取
2. 判断该事件的产业链位置（上游/中游/下游）
3. 分析对相关公司的影响

### 步骤5：输出
- 当日 Top10 热点主题及情绪
- 资金共振板块列表
- 产业链突破点列表（含影响分析）
```

### 2.5 财务体检 Skill

```markdown
# Financial Health Check

## 描述
对单家公司进行全面的财务状况分析。

## 分析流程

### 步骤1：数据获取
1. 从 PostgreSQL 查询目标公司近5年财务数据
2. 计算关键财务比率（ROE、毛利率、净利率、资产负债率、流动比率、存货周转率等）
3. 获取同行业可比公司数据

### 步骤2：趋势分析
1. 判断各财务指标的变化趋势（改善/恶化/稳定）
2. 识别异常波动（单季度变化超过20%）
3. 分析异常波动的原因（从公告/新闻中检索）

### 步骤3：行业对比
1. 将目标公司的关键指标与行业中位数对比
2. 生成雷达图数据（盈利能力、成长能力、偿债能力、运营能力、现金流）
3. 给出行业内的相对位置排名

### 步骤4：风险检测
1. 应收账款/营收占比过高（>30%预警）
2. 存货/营收占比异常
3. 商誉/净资产占比过高（>30%预警）
4. 经营现金流持续为负

### 步骤5：输出
输出财务体检报告，包含：
- 综合评分（百分制）
- 雷达图数据
- 优势指标（3-5个）
- 风险指标（3-5个）
- 与上期相比的变化
```

## 3. 如何调用 Skill

### 3.1 Codex CLI 直接调用

```bash
# 用户输入任何自然语言，Codex 自动匹配对应 Skill
codex "分析半导体行业的产业链上下游关系"
# → 自动触发 industry-chain-analysis Skill

codex "帮我总结中芯国际最近的券商研报观点"  
# → 自动触发 research-summary Skill

codex "今天市场上有哪些热点？"
# → 自动触发 hotspot-detection Skill
```

### 3.2 Web 前端通过 API 间接调用

```python
# backend/app/api/v1/agent.py
from fastapi import APIRouter
import subprocess

router = APIRouter()

@router.post("/analyze/chain")
async def analyze_chain(industry: str):
    """调用 Codex CLI 执行产业链分析 Skill"""
    # Codex CLI 支持通过 stdin 接收任务
    result = subprocess.run(
        ["codex", "--non-interactive", "--task", 
         f"分析 {industry} 行业的产业链上下游关系，输出 JSON 格式结果"],
        capture_output=True, text=True, timeout=300
    )
    return {"industry": industry, "result": result.stdout}
```

### 3.3 定时任务自动执行

```python
# collector/tasks.py - Celery 定时调用 Skill
@app.task
def run_industry_chain_analysis(industry: str):
    """每周自动执行产业链分析 Skill"""
    result = subprocess.run(
        ["codex", "--non-interactive", "--task",
         f"对 {industry} 行业进行产业链分析，将结果写入 data/analysis/{industry}.json"],
        capture_output=True, timeout=600
    )
    return result.returncode
```

## 4. Skill vs LangGraph 对比

| 维度 | LangGraph 方案 | Skill 方案 |
|------|---------------|------------|
| **开发方式** | 写 Python 代码定义 Graph | 写 SKILL.md 自然语言描述 |
| **学习成本** | 需要理解 StateGraph/Node/Edge | 只需要写清楚分析步骤 |
| **修改迭代** | 改代码 → 测试 → 部署 | 改 Markdown → 即时生效 |
| **LLM 调用** | 需自行集成 LangChain | Codex CLI 内置 GPT 调度 |
| **工具集成** | 需手动注册 @tool | 声明即可，Codex 自动调用 |
| **图编排** | 显式定义执行顺序 | 自然语言描述，LLM 自动编排 |
| **灵活性** | 精确控制流程 | 依赖 LLM 理解，可能有偏差 |
| **适用场景** | 需要精确流水线的场景 | 需要快速迭代的分析场景 |
| **Skill 共享** | 不适用 | 可直接分享 SKILL.md 给他人 |

## 5. 推荐方案：Skill 优先 + LangGraph 兜底

```
                    ┌──────────────────┐
                    │   用户请求         │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Codex Skill 匹配  │
                    │  (自然语言→分析)   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌───────────┐  ┌──────────────┐
    │ 70% 场景     │  │ 20% 场景  │  │ 10% 场景      │
    │ Skill 直接   │  │ Skill +   │  │ LangGraph     │
    │ 搞定         │  │ 人工微调   │  │ 精确控制      │
    └─────────────┘  └───────────┘  └──────────────┘
```

**策略**：
- 分析类任务：优先用 Skill，修改快速、无需写代码
- 数据采集类：用 Scrapy + Celery（已设计好，不需频繁改动）
- 前端交互类：用 React（标准工程化方式）
- 需要精确控制的多步推理：才用 LangGraph

大部分新增的分析需求只需要新增或修改一个 SKILL.md，不需要改动代码。
