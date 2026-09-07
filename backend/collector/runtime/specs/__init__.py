"""TaskSpec 声明表：按数据类型族分模块声明，此处聚合供 registry 消费。

新增采集任务只需在对应数据类型模块的 ``SPECS`` 增加一条声明：

- name: 任务名（TASK_MAP 键，与 collector_task.task_type 对应）
- label: 中文展示名（任务目录 API / 管理端 UI 的唯一来源，禁止在前端另行硬编码）
- data_type: 写入 collector_log/渠道解析的数据类型；支持 {param} 占位
  （如 kline 的 "kline_{period}"）
- collectors: source -> "module:Class" 懒加载路径（避免引入 akshare 等重依赖）
- config_params: 透传进采集器 config 的任务参数（含未提供时的 None）
- run_params: 透传进 collector.run(**kwargs) 的任务参数
- defaults: 参数默认值（调用方未提供或显式 None 时生效）
- converters: 参数转换器（值非 None 时应用，如 trade_date -> date）

runner 的任务参数白名单同样从声明表派生，参数只在声明表维护一处。
"""

from collector.runtime.specs.ai import SPECS as AI_SPECS
from collector.runtime.specs.base import TaskSpec
from collector.runtime.specs.fund_flow import SPECS as FUND_FLOW_SPECS
from collector.runtime.specs.fundamental import SPECS as FUNDAMENTAL_SPECS
from collector.runtime.specs.kline import SPECS as KLINE_SPECS
from collector.runtime.specs.maintenance import SPECS as MAINTENANCE_SPECS
from collector.runtime.specs.market import SPECS as MARKET_SPECS
from collector.runtime.specs.news import SPECS as NEWS_SPECS
from collector.runtime.specs.pool import SPECS as POOL_SPECS

__all__ = ["ALL_SPECS", "TaskSpec"]

ALL_SPECS: tuple[TaskSpec, ...] = (
    *KLINE_SPECS,
    *MARKET_SPECS,
    *POOL_SPECS,
    *FUND_FLOW_SPECS,
    *NEWS_SPECS,
    *FUNDAMENTAL_SPECS,
    *AI_SPECS,
    *MAINTENANCE_SPECS,
)
