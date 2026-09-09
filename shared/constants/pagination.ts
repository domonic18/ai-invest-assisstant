/** 分页 pageSize 档位（全站默认值统一来源，业务上限仍由后端 Query 约束）。 */
export const PAGE_SIZE = {
  /** 详情页内嵌列表（研报摘要等辅助信息） */
  inline: 5,
  /** 常规分页列表 */
  list: 10,
  /** 管理端表格 */
  table: 20,
  /** 信息流（电报等） */
  feed: 30,
  /** 大批量信号卡 */
  bulk: 200,
}
