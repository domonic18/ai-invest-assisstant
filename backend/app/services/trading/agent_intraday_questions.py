"""盘中执行 L1 判断题面（批次 8，paper-trading-plan §11.6）。

题面是代码契约不是 prompt 资产：不走 YAML prompt 体系，模块级常量直构
Judge 题型（schema 校验兜底形状）。文案改动等价于换了评测基准——影子期
校准数据以题面版本为语境，改题面前先评估观测数据连续性。
"""

from app.core.decision_model.contracts import (
    JudgeChoice,
    JudgeNoul,
    JudgeNoulCriteria,
    JudgeScore,
)

#: Choice 动作选项（criteria 键即答案值，observation.action 语义对齐）
CHOICE_ACTION_EXECUTE = "立即执行"
CHOICE_ACTION_WAIT = "等待回踩"
CHOICE_ACTION_ABANDON = "放弃本档"

CHOICE_INTRADAY_ACTION = JudgeChoice(
    instructions=(
        "你是 A 股盘中交易执行器。结合行情状态中的分时与大盘环境，"
        "对给定交易计划选出此刻最合理的唯一动作。"
    ),
    criteria={
        CHOICE_ACTION_EXECUTE: "正处计划触发区，分时与盘面不反对立即成交",
        CHOICE_ACTION_WAIT: "方向成立但时机未到（偏离买点/分时过热），等待更好价位",
        CHOICE_ACTION_ABANDON: "触发前提失效（破位/逻辑破坏/环境恶化），放弃本档",
    },
)

NOUL_BUY_TIMING = JudgeNoul(
    instructions="判断此刻该标的的分时形态是否支持按计划买入。",
    criteria=JudgeNoulCriteria(
        true="分时强势整理或回踩企稳，量价配合支持买入",
        false="分时破位下行、放量杀跌或无企稳迹象",
    ),
)

NOUL_EXIT_TIMING = JudgeNoul(
    instructions="判断此刻该标的的分时形态是否支持按计划卖出（止盈/止损）。",
    criteria=JudgeNoulCriteria(
        true="上涨动能衰竭、反抽无力或已破位，支持离场",
        false="仍在强势上行，或止损/止盈依据不成立",
    ),
)

SCORE_MARKET_SUPPORT = JudgeScore(
    instructions="评估当前大盘环境对该计划执行的支持度（1 极弱 - 5 极强）。",
    criteria=[
        "1 大盘恐慌杀跌，不宜任何新动作",
        "2 大盘弱势，仅支持明确的止损离场",
        "3 大盘中性震荡，可中性执行",
        "4 大盘强势，支持顺势执行",
        "5 大盘极强且主线共振，可积极执行",
    ],
)
