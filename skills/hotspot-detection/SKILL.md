---
name: hotspot-detection
description: 市场热点检测：聚合近期新闻、分析情绪与资金流、交叉产业链突破信号，输出热点板块排行与可操作洞察。当用户问"今天什么热门/热点/资金流向哪/市场情绪/异动"时使用。
---

# 市场热点检测

## 描述
通过聚合新闻、分析情绪、交叉对比资金流向与产业链突破信号，实时跟踪市场热点，输出包含可操作洞察的热点看板。

## 触发条件
- 用户询问今天市场热点
- 用户想了解 trending 主题或板块
- 用户询问市场情绪或资金异常
- 关键词：热点、热门、资金流向、情绪、异动、hotspot、trending

## 分析流程

### 步骤 1：新闻聚合
1. 查询 Elasticsearch `announcements` 索引最近 24 小时新闻（限制 200 条）
2. 按行业标签与关键词聚类
3. 计算热度分 = 新闻数 × 时间权重 × 重要性权重
4. 识别前 10 大热点主题

### 步骤 2：情绪分析
对每个热点主题聚类：
1. 将每篇文章分类为正面 / 负面 / 中性
2. 计算情绪比例（正面 / 总数）
3. 提取正面驱动因素与负面担忧
4. 给出整体情绪得分（-1.0 到 +1.0）

### 步骤 3：资金流向交叉验证
1. 查询 PostgreSQL `fund_flow` 获取今日板块资金流向
2. 将热点主题与资金流板块匹配
3. 标记"资金+情绪共振"（热点新闻且大幅净流入）
4. 标记"背离"（热点新闻但净流出，或冷门新闻但净流入）

### 步骤 4：产业链突破信号扫描
在热点新闻中扫描突破信号：
- 技术："突破" "量产" "首发" "自主可控" "国产替代"
- 产能："扩产" "投产" "产能" "新产线"
- 政策："政策" "补贴" "规划" "支持"
- 产品："新品" "发布" "通过认证"

对每条突破：
1. 判断影响的产业链环节
2. 识别受影响上市公司
3. 估算影响幅度（高/中/低）
4. 写一句话影响摘要

### 步骤 5：输出
```json
{
  "analyzed_at": "2026-07-05T15:30:00Z",
  "hot_topics": [
    {
      "topic": "AI芯片",
      "hotness_score": 95,
      "news_count": 28,
      "sentiment": 0.72,
      "sentiment_label": "积极",
      "capital_flow_match": true,
      "sector_net_inflow_billion": 28.5,
      "key_drivers": ["英伟达发布新一代GPU", "国产AI芯片出货量翻倍"],
      "related_companies": ["688256", "688041", "688047"]
    }
  ],
  "sentiment_cross_section": {
    "most_positive_sector": "半导体",
    "most_negative_sector": "房地产",
    "divergence_alerts": [
      {"sector": "新能源", "sentiment": "积极", "capital_flow": "净流出", "alert": "情绪与资金背离"}
    ]
  },
  "capital_flow_top": {
    "inflow_top3": [
      {"sector": "半导体", "net_inflow": 28.5},
      {"sector": "AI概念", "net_inflow": 22.1},
      {"sector": "医药", "net_inflow": 18.3}
    ],
    "outflow_top3": [
      {"sector": "房地产", "net_outflow": 15.2},
      {"sector": "银行", "net_outflow": 12.8}
    ]
  },
  "breakthroughs": [
    {
      "event": "国产5nm刻蚀机通过验证",
      "sector": "半导体设备",
      "chain_position": "上游-设备制造",
      "impact_level": "high",
      "affected_companies": ["002371", "688012"],
      "summary": "国产刻蚀设备突破5nm制程，将加速晶圆厂国产设备导入"
    }
  ],
  "summary": "今日市场热点集中在AI芯片和半导体设备..."
}
```

## 可用工具
- Elasticsearch：新闻搜索与聚合
- PostgreSQL：资金流数据
- Python 3：聚类与情绪打分
- Milvus：将突破信号与公司上下文匹配

## 预期输出
保存到 `data/analysis/hotspot/hotspot_{date}.json`，并生成 Markdown 摘要供前端展示。

## 备注
- 交易时段每 30 分钟自动运行一次
- 交叉验证交易所官方公告
- 对未经证实的传闻标注"待确认"
