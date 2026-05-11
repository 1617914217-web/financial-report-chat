// 财务意图分类
export type IntentLabel =
  | 'balance_sheet'
  | 'income_sheet'
  | 'core_performance_indicators_sheet'
  | 'stock_income_statement_data'
  | 'multiple_tables'
  | 'unanswerable'

// 思考步骤
export interface ThinkingStep {
  step: string
  detail: string
}

// 单条聊天消息
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  intent?: IntentLabel
  sql?: string
  data?: QueryResult
  steps?: ThinkingStep[]
  timestamp: number
}

// 数据库查询结果
export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  rowCount: number
  sql: string
}

// 知识库文档
export interface KBDocument {
  id: string
  title: string
  type: 'pdf' | 'doc' | 'url' | 'note'
  tags: string[]
  createdAt: string
  updatedAt: string
  summary?: string
}

// 数据库表元信息
export interface TableInfo {
  name: string
  label: string
  rowCount: number
  columns: { name: string; type: string; comment: string }[]
}

// 意图识别响应
export interface IntentResponse {
  intent: IntentLabel
  confidence: number
  field?: string
}

// 用户信息
export interface UserInfo {
  username: string
  avatar?: string
}

// 对话状态
export interface ChatState {
  messages: ChatMessage[]
  isTyping: boolean
  user: UserInfo | null
  setUser: (u: UserInfo | null) => void
  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  setTyping: (v: boolean) => void
  clearMessages: () => void
}
