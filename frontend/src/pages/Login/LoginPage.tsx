import { useState } from 'react'
import { Input, Button, message } from 'antd'
import { UserOutlined, LockOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useChatStore } from '../../store/useChatStore'
import './LoginPage.css'

export default function LoginPage() {
  const { setUser } = useChatStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  function handleLogin() {
    if (!username.trim()) {
      message.warning('请输入用户名')
      return
    }
    if (!password.trim()) {
      message.warning('请输入密码')
      return
    }
    setLoading(true)
    // 模拟登录（本地认证，密码任意或校验简单规则）
    setTimeout(() => {
      const saved = localStorage.getItem('finqa_user')
      if (saved) {
        try {
          const users = JSON.parse(saved)
          const match = users.find((u: { username: string; password: string }) => u.username === username.trim() && u.password === password)
          if (match) {
            setUser({ username: match.username })
            localStorage.setItem('finqa_current_user', match.username)
            message.success(`欢迎回来，${match.username}`)
            setLoading(false)
            return
          }
        } catch { /* ignore */ }
      }
      // 新用户直接注册
      const users: { username: string; password: string }[] = saved ? JSON.parse(saved) : []
      users.push({ username: username.trim(), password })
      localStorage.setItem('finqa_user', JSON.stringify(users))
      localStorage.setItem('finqa_current_user', username.trim())
      setUser({ username: username.trim() })
      message.success(`欢迎，${username.trim()}`)
      setLoading(false)
    }, 400)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') handleLogin()
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <ThunderboltOutlined />
        </div>
        <h1 className="login-title">财报智能问答系统</h1>
        <p className="login-subtitle">Financial Report Intelligent QA</p>
        <div className="login-form">
          <Input
            size="large"
            prefix={<UserOutlined style={{ color: '#5a6a8a' }} />}
            placeholder="请输入用户名"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Input.Password
            size="large"
            prefix={<LockOutlined style={{ color: '#5a6a8a' }} />}
            placeholder="请输入密码"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Button
            type="primary"
            size="large"
            className="login-btn"
            loading={loading}
            onClick={handleLogin}
            block
          >
            登录 / 注册
          </Button>
        </div>
        <p className="login-footer">首次登录将自动注册账号</p>
      </div>
    </div>
  )
}
