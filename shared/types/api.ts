/** 跨域通用 wire 类型（分页信封 / 通用集合），各域类型见同目录域文件。 */
export interface ApiPaginatedResponse<T> {
  total: number
  page: number
  pageSize: number
  items: T[]
}

/** 已生成分析/检测数据的交易日列表（升序），日历打点用。 */
export interface ApiTradeDatesResponse {
  tradeDates: string[]
}
