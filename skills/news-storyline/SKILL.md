---
name: news-storyline
description: 事件故事线建线/续接：把近 48h 高重要度（≥70 分）未入线资讯按同一事件聚合为故事线（≥5 篇报道建线），续接既有跟踪线并更新状态与最新进展，供资讯中心「重点与跟踪」视图。仅定时任务路径（news-storyline）执行，无侧边栏手动交互。
allowed-tools: []
---

# 事件故事线建线续接

## 描述
对批量输入的高重要度资讯候选按「同一事件」聚类：够 5 篇的新事件建新线，
不足 5 篇但明确属于既有线的报道续接该线。输入由服务层按「近 48h、score≥70、
未入任何线」批量构造（含 source / item_id / title / content 节选 / category /
stock_codes / score / publish_time），单轮候选不超过 40 条。

## 触发条件
- 定时任务 `news-storyline`（盘中每 30 分钟）：对候选电报聚类建线/续接

## 聚类规则
- 同一事件 = 围绕同一政策/事故/公告/发牌等具体事件的连续报道
- 新建线阈值：候选中 ≥5 篇；不足 5 篇仅可续接既有线
- 孤条不输出，留待后续报道增多再聚

## 输出 Schema
```json
{
  "new_storylines": [
    {
      "title": "央行降准落地",
      "summary": "降准 50bp 释放流动性，银行地产链受益",
      "status": "tracking",
      "latest_brief": "降准落地，官宣释放约 1 万亿长期资金",
      "item_refs": [{"source": "cls_telegraph", "item_id": "1234567"}]
    }
  ],
  "attachments": [
    {
      "storyline_id": 12,
      "status": "near_end",
      "latest_brief": "美联储如期降息 25bp",
      "item_refs": [{"source": "cls_telegraph", "item_id": "1234599"}]
    }
  ]
}
```
- item_refs 的 source/item_id 原样取自输入，禁止编造
- storyline_id 必须取自输入既有线
- status：tracking（仍在演进）/ near_end（接近尾声）/ finished（已了结）
