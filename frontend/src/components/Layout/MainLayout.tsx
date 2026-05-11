import { useState } from 'react'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { Badge, Tooltip } from 'antd'
import {
  MessageOutlined,
  BookOutlined,
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ThunderboltOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useChatStore } from '../../store/useChatStore'
import './MainLayout.css'

interface NavItem {
  key: string
  label: string
  icon: React.ReactNode
  badge?: number
}

const NAV_ITEMS: NavItem[] = [
  { key: '/chat', label: '智能问答', icon: <MessageOutlined /> },
  { key: '/knowledge', label: '知识库', icon: <BookOutlined />, badge: 5 },
  { key: '/database', label: '数据库', icon: <DatabaseOutlined /> },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const { user, setUser } = useChatStore()

  function handleLogout() {
    setUser(null)
    localStorage.removeItem('finqa_current_user')
    navigate('/login')
  }

  return (
    <div className="app-layout">
      {/* 侧边栏 */}
      <aside className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
        {/* Logo */}
        <div className="sidebar-logo" onClick={() => navigate('/chat')}>
          <div className="logo-icon">
            <ThunderboltOutlined style={{ fontSize: 18, color: '#00d4ff' }} />
          </div>
          {!collapsed && <span className="logo-text">财报问答</span>}
        </div>

        {/* 导航 */}
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <div
              key={item.key}
              className={`nav-item ${location.pathname === item.key ? 'nav-item-active' : ''}`}
              onClick={() => navigate(item.key)}
              title={collapsed ? item.label : undefined}
            >
              <span className="nav-icon">
                {item.badge ? (
                  <Badge count={item.badge} size="small" offset={[6, -4]}>
                    {item.icon}
                  </Badge>
                ) : item.icon}
              </span>
              {!collapsed && <span className="nav-label">{item.label}</span>}
            </div>
          ))}
        </nav>

        {/* 底部用户区 */}
        <div className="sidebar-footer">
          {/* 用户信息 */}
          {!collapsed && user && (
            <div className="sidebar-user">
              <div className="sidebar-user-avatar">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div className="sidebar-user-info">
                <span className="sidebar-user-name">{user.username}</span>
                <span className="sidebar-user-role">分析师</span>
              </div>
              <Tooltip title="退出登录" placement="right">
                <div className="sidebar-logout" onClick={handleLogout}>
                  <LogoutOutlined style={{ fontSize: 13 }} />
                </div>
              </Tooltip>
            </div>
          )}
          {collapsed && user && (
            <Tooltip title={`${user.username} (点击退出)`} placement="right">
              <div className="sidebar-user-collapsed" onClick={handleLogout}>
                {user.username.charAt(0).toUpperCase()}
              </div>
            </Tooltip>
          )}
          {/* 折叠按钮 */}
          <div
            className="collapse-btn"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? '展开' : '收起'}
          >
            {collapsed
              ? <MenuUnfoldOutlined style={{ fontSize: 16 }} />
              : <MenuFoldOutlined style={{ fontSize: 16 }} />}
          </div>
        </div>
      </aside>

      {/* 主内容 */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
