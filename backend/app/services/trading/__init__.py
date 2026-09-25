"""模拟盘交易域服务（sidecar 客户端 / 盘后同步 / 本地查询）。

柜台（掘金仿真）是交易状态真相源，本地表是复盘分析与计划执行的真相源；
本包只依赖 sidecar HTTP 与 models，禁止导入 agent/skills/runtime。
"""
