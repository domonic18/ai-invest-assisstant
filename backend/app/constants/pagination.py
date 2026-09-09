"""分页与列表 limit 档位常量（api 路由默认值/上限的单一来源）。"""

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

DEFAULT_HISTORY_LIMIT = 10
MAX_HISTORY_LIMIT = 50

# 板块资金流是当日有界清单（行业 ~90 + 概念 ~430），热点页信号卡需单页拉全量
MAX_SECTOR_PAGE_SIZE = 500
