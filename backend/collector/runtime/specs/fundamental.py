"""基本面与基础资料任务声明：清单/股本/概念映射/公司资料/公告/财报/IPO/基金持仓/研报。"""

from collector.runtime.specs.base import TaskSpec

SPECS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="stock-list",
        label="股票列表",
        data_type="stock_list",
        collectors={
            "sina": "collector.spiders.sina_stock_list:SinaStockListCollector",
        },
        queue="heavy",
        soft_time_limit=1800,
    ),
    TaskSpec(
        name="stock-shares",
        label="股本数据",
        data_type="stock_shares",
        collectors={
            "tushare": "collector.spiders.tushare_stock_basic:TushareStockBasicCollector",
        },
        config_params=(),
    ),
    TaskSpec(
        name="financial-statement",
        label="财务报表",
        data_type="financial_statement_em",
        collectors={
            "eastmoney": (
                "collector.spiders.eastmoney_financial_statement:"
                "EastmoneyFinancialStatementCollector"
            ),
        },
        config_params=("report_types",),
    ),
    TaskSpec(
        name="concept-constituents",
        label="概念成分股",
        data_type="mapping_stock_concept",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_concept_constituents:EastmoneyConceptConstituentCollector",
        },
    ),
    TaskSpec(
        name="company-profile",
        label="公司概况",
        data_type="company_profile",
        collectors={
            "cninfo": "collector.spiders.cninfo_profile:CninfoProfileCollector",
        },
    ),
    TaskSpec(
        name="disclosure",
        label="公告披露",
        data_type="disclosure",
        collectors={
            "cninfo": "collector.spiders.cninfo_disclosure:CninfoDisclosureCollector",
        },
        run_params=("start_date", "end_date"),
    ),
    TaskSpec(
        name="financial-report",
        label="财报",
        data_type="financial_statement",
        collectors={
            "cninfo": "collector.spiders.cninfo_financial_report:CninfoFinancialReportCollector",
        },
        config_params=("report_types", "start_date", "end_date"),
    ),
    TaskSpec(
        name="ipo-info",
        label="IPO 信息",
        data_type="ipo_info",
        collectors={"cninfo": "collector.spiders.cninfo_ipo:CninfoIpoCollector"},
    ),
    TaskSpec(
        name="fund-holdings",
        label="基金持仓",
        data_type="fund_holding",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_fund_holdings:EastMoneyFundHoldingsCollector",
        },
        config_params=("report_date",),
    ),
    TaskSpec(
        name="research-report",
        label="个股研报",
        data_type="research_report",
        collectors={
            "eastmoney": "collector.spiders.eastmoney_research_report:EastMoneyResearchReportCollector",
        },
        run_params=("start_date", "end_date"),
    ),
)
