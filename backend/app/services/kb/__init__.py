"""知识库域服务层（F-KB）。

依赖方向约定：本包禁止顶层导入 ``app.agent.tools/skills/runtime``
（它们反向依赖 services，需在函数内延迟导入）；``app.agent.core``
纯配置叶子可顶层导入。
"""
