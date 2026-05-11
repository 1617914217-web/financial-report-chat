// 工具函数

/** 生成唯一ID */
export function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/** 格式化时间戳 */
export function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/** 意图标签 → 中文展示 */
export const intentLabelMap: Record<string, string> = {
  balance_sheet: '🏦 资产负债表',
  income_sheet: '📊 利润表',
  core_performance_indicators_sheet: '📈 核心指标',
  stock_income_statement_data: '💹 个股行情',
  multiple_tables: '🔗 跨表查询',
  unanswerable: '❓ 暂无法回答',
}

/** 表名 → 中文展示 */
export const tableLabelMap: Record<string, string> = {
  balance_sheet: '资产负债表',
  income_sheet: '利润表',
  core_performance_indicators_sheet: '核心指标表',
  stock_income_statement_data: '个股行情数据',
}

/** 格式化数字（金额） */
export function formatMoney(val: unknown, decimals = 2): string {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (isNaN(num)) return String(val)
  return num.toLocaleString('zh-CN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** 格式化百分比（值已经是百分比的用此函数） */
export function formatPercentDirect(val: unknown): string {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (isNaN(num)) return String(val)
  return `${num.toFixed(2)}%`
}

/** 格式化百分比（值是小数0-1，需乘100） */
export function formatPercent(val: unknown): string {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (isNaN(num)) return String(val)
  // 如果值已经是百分比值（大于1），直接显示
  if (Math.abs(num) > 1) return `${num.toFixed(2)}%`
  return `${(num * 100).toFixed(2)}%`
}

/** 格式化报告日期 */
export function formatDate(d: unknown): string {
  if (!d) return '-'
  return String(d).replace(/(\d{4})(\d{2})(\d{2})/g, '$1-$2-$3')
}
