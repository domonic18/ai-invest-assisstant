---
name: watchlist-screenshot-recognition
description: 自选股截图识别：从券商 App 自选列表、行情列表等截图中识别 A 股代码与名称。经自选股页「截图导入」REST 端点触发，非助手 agent 工具，助手对话中不应尝试调用。
---

# 自选股截图识别

## 描述
从股票截图（券商 App 自选列表、行情列表等）中识别 A 股代码与名称，用于自选股批量导入。

## 触发条件
- 用户在自选股页使用「截图导入」功能上传截图
- 本 Skill 经 REST 端点（POST /users/watchlist/import-screenshot）同步触发，
  不在助手 agent 的工具集内；对话中用户请求识别截图时，请引导其使用自选股页的截图导入入口。
