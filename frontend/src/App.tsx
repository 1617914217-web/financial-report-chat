import { useEffect } from 'react'
import { ConfigProvider, App as AntApp } from 'antd'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import ChatPage from './pages/Chat/ChatPage'
import KnowledgeBasePage from './pages/KnowledgeBase/KnowledgeBasePage'
import DatabasePage from './pages/Database/DatabasePage'
import LoginPage from './pages/Login/LoginPage'
import { useChatStore } from './store/useChatStore'

const darkTheme = {
  token: {
    colorPrimary: '#1677ff',
    colorBgBase: '#0a0e27',
    colorTextBase: '#e8eaf6',
    colorBorder: '#1e2a4a',
    colorBgContainer: '#111827',
    borderRadius: 8,
    fontFamily: "'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif",
  },
  components: {
    Table: {
      headerBg: '#1a2544',
      rowHoverBg: '#1a2544',
      borderColor: '#1e2a4a',
      colorBgContainer: '#0d1117',
      colorText: '#c8d0e8',
      colorTextSecondary: '#8a9bcf',
    },
    Tabs: {
      itemColor: '#5a6a8a',
      itemSelectedColor: '#1677ff',
      inkBarColor: '#1677ff',
      itemHoverColor: '#e8eaf6',
    },
    Drawer: {
      colorBgElevated: '#0a0e27',
    },
  },
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const user = useChatStore(s => s.user)
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const user = useChatStore(s => s.user)
  const setUser = useChatStore(s => s.setUser)

  // 自动恢复登录状态
  useEffect(() => {
    if (!user) {
      const saved = localStorage.getItem('finqa_current_user')
      if (saved) {
        setUser({ username: saved })
      }
    }
  }, [])

  return (
    <ConfigProvider theme={darkTheme}>
      <AntApp>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={user ? <Navigate to="/chat" replace /> : <LoginPage />} />
            <Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
              <Route index element={<Navigate to="/chat" replace />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="knowledge" element={<KnowledgeBasePage />} />
              <Route path="database" element={<DatabasePage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}
