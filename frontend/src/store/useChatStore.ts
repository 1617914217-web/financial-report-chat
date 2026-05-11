import { create } from 'zustand'
import type { ChatMessage, ChatState, UserInfo } from '../types'
import { uid } from '../utils'

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isTyping: false,
  user: null,

  setUser: (u: UserInfo | null) => set({ user: u }),

  addMessage: (msg) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { ...msg, id: uid(), timestamp: Date.now() } as ChatMessage,
      ],
    })),

  setTyping: (v) => set({ isTyping: v }),

  clearMessages: () =>
    set({
      messages: [
        {
          id: uid(),
          role: 'system',
          content: '欢迎使用财报智能问答系统，请输入您想查询的财务问题。',
          timestamp: Date.now(),
        },
      ],
    }),
}))
