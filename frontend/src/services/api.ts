import axios from 'axios'
import type { IntentResponse, QueryResult, ThinkingStep } from '../types'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

/** 意图识别 */
export async function recognizeIntent(question: string): Promise<IntentResponse> {
  const res = await http.post<{ intent: string; confidence: number }>('/intent', { question })
  return res.data as IntentResponse
}

/** 查询数据库（对话式） */
export async function chatQuery(question: string): Promise<{ answer: string; sql?: string; data?: QueryResult; steps?: ThinkingStep[]; intent?: string; slots?: Record<string, string> }> {
  const res = await http.post<{ answer: string; sql?: string; data?: QueryResult; steps?: ThinkingStep[]; intent?: string; slots?: Record<string, string> }>('/chat', { question })
  return res.data
}

/** 纯 SQL 执行 */
export async function executeSQL(sql: string): Promise<QueryResult> {
  const res = await http.post<QueryResult>('/sql', { sql })
  return res.data
}

/** 获取数据库表列表 */
export async function getTables() {
  const res = await http.get('/tables')
  return res.data
}

/** 预览某表数据 */
export async function previewTable(table: string, limit = 5) {
  const res = await http.get(`/tables/${table}/preview`, { params: { limit } })
  return res.data
}
