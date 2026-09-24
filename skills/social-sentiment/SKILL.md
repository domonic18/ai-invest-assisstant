---
name: social-sentiment
description: 社媒大V情绪判断：对追踪的财经大V视频内容（口播转写/标题/文案）批量判断市场相关性与多空立场，输出立场、置信度、核心论点、影响标的与一句话摘要，供资讯中心「大V情绪」流与账号维度视图。仅定时任务路径（social-sentiment）执行，无侧边栏手动交互。
allowed-tools: []
---

# 社媒大V情绪判断

## 描述
对批量输入的大V视频条目逐条判断：
1. **相关性**（relevance）：内容是否与证券市场相关。生活日常/广告带货/纯娱乐内容为 false，此类不进入情绪流。
2. **多空立场**（stance）：bullish（看多）/ bearish（看空）/ neutral（中性或纯信息播报）。
3. **置信度**（confidence）：0-1，立场表达越明确越高；观点模糊或仅陈述事实给低置信度。
4. **核心论点**（core_arguments）：每条一句话，忠实于博主原话，禁止脑补。
5. **影响标的**（targets）：博主明确提到的大盘指数/行业板块/个股/大宗商品，无则空数组。
6. **一句话摘要**（summary）：≤60 字，概括观点与理由。

输入由服务层按「未判且启用账号」批量构造（post_id / title / caption /
topic_tags / transcript 口播转写 / transcript_missing），每批不超过 20 条；
文稿缺失时以标题与文案为判断依据并在结论中保持谨慎。

## 触发条件
- 定时任务 `social-sentiment`（每 10 分钟）：对待判内容批量判断，判后文稿立即清除

## 判断要点
- 口播转写是主要内容依据，标题/文案/话题标签为辅助
- 情绪词（"看多""要崩""巨震"）结合上下文判断，反讽/疑问语气不轻易定方向
- 个股标的尽量给出 A 股代码；不存在的代码宁可不输出（服务层会过滤不在基本表的代码）
- 大盘观点 targets 用 type=index（如 "上证指数"）；板块观点 type=sector；商品观点（黄金/原油）type=commodity

## 输出 Schema
```json
{
  "items": [
    {
      "post_id": 123,
      "relevance": true,
      "stance": "bearish",
      "confidence": 0.85,
      "core_arguments": ["量能持续萎缩，反弹缺乏承接"],
      "targets": [{"target_type": "index", "name": "上证指数", "code": null}],
      "summary": "看空大盘：量能萎缩反弹乏力，短期或继续探底"
    }
  ]
}
```
- 每条输入必须对应一条输出，post_id 原样返回，禁止编造输入之外的条目
- 判为不相关（relevance=false）的条目 stance 给 neutral、targets 空数组，不省略
