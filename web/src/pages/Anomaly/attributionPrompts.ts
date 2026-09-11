/**
 * AI 归因手动触发的问题预置文案：目标清单（含规则事实）随问题带给助手 agent，
 * 与 skills/anomaly-attribution 的「items 必须覆盖输入清单」契约配套。
 */

import type { ApiSectorAnomalyItem, ApiStockAnomalyItem } from '@ai-invest/shared'

import { describeAnomalyTypes, SECTOR_CATEGORY_LABELS, STOCK_CATEGORY_LABELS } from './labels'

function sectorTarget(it: ApiSectorAnomalyItem, idx?: number): string {
  const head = idx === undefined ? '' : `${idx + 1}. `
  return (
    `${head}${it.sectorName}（${it.sectorType}:${it.sectorCode}，` +
    `命中 ${describeAnomalyTypes(it.anomalyTypes)}，强度 ${it.strength}，` +
    `当前分类：${SECTOR_CATEGORY_LABELS[it.attributionCategory ?? ''] ?? '未分类'}）`
  )
}

function stockTarget(it: ApiStockAnomalyItem, idx?: number): string {
  const head = idx === undefined ? '' : `${idx + 1}. `
  return (
    `${head}${it.stockName}（${it.stockCode}，` +
    `命中 ${describeAnomalyTypes(it.anomalyTypes)}，强度 ${it.strength}，` +
    `当前分类：${STOCK_CATEGORY_LABELS[it.attributionCategory ?? ''] ?? '未分类'}）`
  )
}

export function sectorAttributionPrompt(
  tradeDate: string | undefined,
  items: ApiSectorAnomalyItem[],
): string {
  const dateLabel = tradeDate ?? '最近交易日'
  if (items.length === 1) {
    const it = items[0]
    return (
      `请对 ${dateLabel} 的板块异动「${sectorTarget(it)}」进行 AI 归因，` +
      '请按 anomaly-attribution 技能调用证据工具核实后，调用 persist_sector_anomaly_attribution 工具落库。'
    )
  }
  const list = items.map((it, idx) => sectorTarget(it, idx)).join('；')
  return (
    `请对 ${dateLabel} 的板块异动强度榜进行 AI 归因，目标清单：${list}。` +
    '请按 anomaly-attribution 技能调用证据工具核实后给出每条的归因分类与摘要，' +
    '并调用 persist_sector_anomaly_attribution 工具落库。'
  )
}

export function stockAttributionPrompt(
  tradeDate: string | undefined,
  items: ApiStockAnomalyItem[],
): string {
  const dateLabel = tradeDate ?? '最近交易日'
  if (items.length === 1) {
    const it = items[0]
    return (
      `请对 ${dateLabel} 的个股异动「${stockTarget(it)}」进行 AI 归因，` +
      '请按 anomaly-attribution 技能调用证据工具（龙虎榜/个股资金/新闻）核实后，' +
      '调用 persist_stock_anomaly_attribution 工具落库。'
    )
  }
  const list = items.map((it, idx) => stockTarget(it, idx)).join('；')
  return (
    `请对 ${dateLabel} 的个股异动强度榜进行 AI 归因，目标清单：${list}。` +
    '请按 anomaly-attribution 技能调用证据工具核实后给出每条的归因分类与摘要，' +
    '并调用 persist_stock_anomaly_attribution 工具落库。'
  )
}
