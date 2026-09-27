import type { ColumnsType } from 'antd/es/table'

type AnyColumn<T> = ColumnsType<T>[number]

function columnId<T>(column: AnyColumn<T>): string {
  const id = 'dataIndex' in column ? (column.key ?? column.dataIndex) : column.key
  return String(id ?? '')
}

/** 窄屏下裁剪 antd 表格列：只保留 keepIds 中的列并去掉固定锚（避免左右固定列在
 * 窄视口把可滚动中间区夹到几乎为零），列顺序保持原有相对顺序。 */
export function narrowColumns<T>(
  columns: ColumnsType<T>,
  keepIds: readonly string[],
): ColumnsType<T> {
  const keep = new Set(keepIds)
  return columns
    .filter((column) => keep.has(columnId(column)))
    .map((column) => ({ ...column, fixed: undefined }) as AnyColumn<T>)
}
