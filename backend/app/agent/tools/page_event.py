"""助手工具 → 页面回写事件协议。

工具返回值中携带 ``__event__`` 标记时，后端流端点（``runs.py``）会在
messages 通道检测到并补发 ``custom`` SSE 事件；前端
``web/src/components/assistant/pageEvents.ts`` 按事件 type 查注册表消费，
驱动对应页面刷新并在对话内渲染「查看结果」按钮。

新增业务域接入步骤：
1. 工具返回值带 ``page_event("<domain>.complete", **标识字段)``；
2. 前端注册表登记 parse 规则与按钮文案；
3. 页面用 ``usePageAssistantResult`` 订阅该事件类型。
"""

from typing import Any


def page_event(event_type: str, **fields: Any) -> dict[str, Any]:
    """构造页面回写事件标记（snake_case 字段，与 SSE custom 事件同构）。"""
    return {"type": event_type, **fields}
