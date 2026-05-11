import { useRef, useEffect, useState } from 'react'
import { Input, Button, Tag, Tooltip, Collapse } from 'antd'
import { SendOutlined, DeleteOutlined, ThunderboltOutlined, DatabaseOutlined, UserOutlined, RobotOutlined } from '@ant-design/icons'
import { useChatStore } from '../../store/useChatStore'
import { chatQuery } from '../../services/api'
import { intentLabelMap, formatMoney, formatPercent, formatDate } from '../../utils'
import type { ChatMessage, QueryResult, ThinkingStep } from '../../types'
import './ChatPage.css'

/** 消息气泡 */
function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const user = useChatStore(s => s.user)

  return (
    <div className={`msg-row ${isUser ? 'msg-user' : 'msg-assistant'} fade-in`}>
      {!isUser && <div className="msg-avatar"><RobotOutlined /></div>}
      <div className="msg-body">
        {!isUser && msg.steps && msg.steps.length > 0 && (
          <ThinkingSteps steps={msg.steps} />
        )}
        {msg.intent && (
          <div className="msg-intent-tag">
            <Tag color="blue" style={{ margin: 0 }}>{intentLabelMap[msg.intent as keyof typeof intentLabelMap] ?? msg.intent}</Tag>
            {msg.data && <Tag color="cyan" icon={<DatabaseOutlined />}>数据库</Tag>}
          </div>
        )}
        <div className={`msg-bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
          {renderContent(msg)}
        </div>
        {msg.sql && (
          <Tooltip title="执行的SQL" placement="left">
            <pre className="msg-sql">/* {msg.intent ? (intentLabelMap[msg.intent as keyof typeof intentLabelMap] ?? '') : ''} */&#10;{msg.sql}</pre>
          </Tooltip>
        )}
      </div>
      {isUser && (
        <div className="msg-avatar-self">
          {user?.username?.charAt(0)?.toUpperCase() ?? <UserOutlined style={{ fontSize: 14 }} />}
        </div>
      )}
    </div>
  )
}

/** 思考过程展示 */
function ThinkingSteps({ steps }: { steps: ThinkingStep[] }) {
  const stepIcons: Record<string, string> = {
    '文本预处理': '🔤',
    '意图分类': '🎯',
    '槽位填充': '🏷️',
    'NL2SQL生成': 'SQL',
    'SQL校验': '✅',
    '数据查询': '📊',
    '结论生成': '💡',
    '错误': '❌',
  }

  return (
    <Collapse
      className="thinking-collapse"
      ghost
      size="small"
      items={[{
        key: 'thinking',
        label: (
          <span className="thinking-label">
            <RobotOutlined style={{ marginRight: 6, color: '#00d4ff' }} />
            思考过程 ({steps.length}步)
          </span>
        ),
        children: (
          <div className="thinking-steps">
            {steps.map((s, i) => (
              <div key={i} className={`thinking-step ${s.step === '错误' ? 'thinking-error' : ''}`}>
                <span className="thinking-step-icon">{stepIcons[s.step] ?? '📋'}</span>
                <span className="thinking-step-name">{s.step}</span>
                <span className="thinking-step-detail">{s.detail}</span>
              </div>
            ))}
          </div>
        ),
      }]}
    />
  )
}

/** 渲染消息内容（含数据表格） */
function renderContent(msg: ChatMessage) {
  if (msg.data) {
    return (
      <>
        <p style={{ marginBottom: 12 }}>{msg.content}</p>
        <DataTable data={msg.data} />
      </>
    )
  }
  return <span>{msg.content}</span>
}

/** 数据表格 */
function DataTable({ data }: { data: QueryResult }) {
  if (!data.rows || data.rows.length === 0) {
    return <div className="data-empty">暂无数据</div>
  }
  const cols = data.columns.filter(c => !['id', 'create_time', 'update_time', 'serial_number'].includes(c))

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {cols.map(c => (
              <th key={c}>{c.replace(/_/g, '\u200b_')}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.slice(0, 20).map((row, i) => (
            <tr key={i}>
              {cols.map(c => (
                <td key={c}>
                  {formatCell(c, row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.rowCount > 20 && (
        <div className="data-table-footer">共 {data.rowCount} 条，仅显示前 20 条</div>
      )}
    </div>
  )
}

function formatCell(col: string, val: unknown): React.ReactNode {
  if (val === null || val === undefined) return <span className="cell-null">-</span>
  const str = String(val)
  if (col.includes('margin') || col.includes('rate') || col.includes('ratio') || col.includes('growth'))
    return <span className="cell-pct">{formatPercent(val)}</span>
  if (col.includes('fund') || col.includes('revenue') || col.includes('profit') || col.includes('asset') || col.includes('cost') || col.includes('expense') || col.includes('income') || col.includes('equity') || col.includes('liability'))
    return <span className="cell-money">{formatMoney(val)}</span>
  if (col.includes('date') || col.includes('report'))
    return <span className="cell-date">{formatDate(val)}</span>
  return str
}

/** 打字指示器 */
function TypingIndicator() {
  return (
    <div className="msg-row msg-assistant fade-in">
      <div className="msg-avatar"><RobotOutlined /></div>
      <div className="msg-body">
        <div className="bubble-assistant typing-bubble">
          <span className="thinking-dot" />
          <span className="thinking-dot" style={{ animationDelay: '0.2s' }} />
          <span className="thinking-dot" style={{ animationDelay: '0.4s' }} />
        </div>
      </div>
    </div>
  )
}

export default function ChatPage() {
  const { messages, isTyping, addMessage, setTyping, clearMessages } = useChatStore()
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<any>(null)

  // 初始化系统消息
  useEffect(() => {
    if (messages.length === 0) {
      clearMessages()
    }
  }, [])

  // 滚动到底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  async function handleSend() {
    const q = input.trim()
    if (!q || isTyping) return
    setInput('')
    addMessage({ role: 'user', content: q })
    setTyping(true)
    try {
      const res = await chatQuery(q)
      addMessage({
        role: 'assistant',
        content: res.answer,
        sql: res.sql,
        data: res.data,
        steps: res.steps,
        intent: res.data ? detectIntent(res.sql ?? '') : undefined,
      })
    } catch (e: unknown) {
      const err = e instanceof Error ? e.message : String(e)
      addMessage({ role: 'assistant', content: `出错了：${err}` })
    } finally {
      setTyping(false)
      inputRef.current?.focus()
    }
  }

  function detectIntent(sql: string): ChatMessage['intent'] {
    const s = sql.toLowerCase()
    if (s.includes('balance_sheet')) return 'balance_sheet'
    if (s.includes('income_sheet')) return 'income_sheet'
    if (s.includes('core_performance')) return 'core_performance_indicators_sheet'
    if (s.includes('stock_income')) return 'stock_income_statement_data'
    if (s.includes('join') || s.includes(',')) return 'multiple_tables'
    return 'unanswerable'
  }

  return (
    <div className="chat-page">
      {/* 顶部标题栏 */}
      <div className="chat-header">
        <div className="chat-header-left">
          <ThunderboltOutlined style={{ color: '#00d4ff', marginRight: 8 }} />
          <span className="chat-title">财报智能问答</span>
        </div>
        <Button type="text" icon={<DeleteOutlined />} onClick={clearMessages} className="clear-btn">
          清空对话
        </Button>
      </div>

      {/* 消息列表 */}
      <div className="chat-messages">
        {messages.map(msg => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="chat-input-area">
        <div className="chat-input-wrap">
          <Input.TextArea
            ref={inputRef}
            className="chat-input"
            placeholder="输入财务问题，如：ST金花2022年的毛利率和净利率是多少？"
            value={input}
            onChange={e => setInput(e.target.value)}
            onPressEnter={e => {
              if (!e.shiftKey) { e.preventDefault(); handleSend() }
            }}
            autoSize={{ minRows: 1, maxRows: 4 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={isTyping}
            className="send-btn"
          >
            发送
          </Button>
        </div>
        <div className="chat-hints">
          示例：
          <span onClick={() => setInput('ST金花2022年的毛利率和净利率是多少？')}>ST金花毛利率</span>
          <span onClick={() => setInput('对比万邦德2022和2023年的营业收入')}>营收对比</span>
          <span onClick={() => setInput('2022年净利润最高的3家公司')}>利润排名</span>
          <span onClick={() => setInput('片仔癀2022年的核心指标')}>核心指标</span>
        </div>
      </div>
    </div>
  )
}
