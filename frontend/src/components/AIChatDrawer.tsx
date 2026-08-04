import { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import type { ChatMessage, ChatSession } from '../api/chat'
import {
  createChatSession,
  deleteChatSession,
  getChatSession,
  listProjectChatSessions,
  sendChatMessage,
} from '../api/chat'

interface AIChatDrawerProps {
  projectId: string
  isOpen: boolean
  onClose: () => void
}

const QUICK_PROMPTS = [
  '帮我完善这个角色设定',
  '这段剧情怎么改更有张力',
  '给这章写个更好的开头',
  '分析一下目前的剧情节奏',
]

function renderMarkdown(content: string): string {
  return marked.parse(content, { async: false }) as string
}

function AIChatDrawer({ projectId, isOpen, onClose }: AIChatDrawerProps) {
  const [sessions, setSessions] = useState([] as ChatSession[])
  const [activeSessionId, setActiveSessionId] = useState(null as string | null)
  const [messages, setMessages] = useState([] as ChatMessage[])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [showSessionList, setShowSessionList] = useState(false)
  const [initLoading, setInitLoading] = useState(false)
  const messagesEndRef = useRef(null as HTMLDivElement | null)

  // 打字机效果状态
  const [displayedTexts, setDisplayedTexts] = useState({} as Record<string, string>)
  const [typingDone, setTypingDone] = useState(new Set<string>())
  const typingIntervalRef = useRef(null as ReturnType<typeof setInterval> | null)

  // 初始化：加载会话列表
  useEffect(() => {
    if (!isOpen || !projectId) return
    const init = async () => {
      setInitLoading(true)
      try {
        const list = await listProjectChatSessions(projectId)
        setSessions(list)
        if (list.length > 0) {
          await loadSession(list[0].id)
        } else {
          const session = await createChatSession(projectId)
          setSessions([session])
          setActiveSessionId(session.id)
          setMessages([])
        }
      } catch (e) {
        console.error('加载 AI 会话失败', e)
      } finally {
        setInitLoading(false)
      }
    }
    init()
  }, [isOpen, projectId])

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadSession = async (sessionId: string) => {
    setLoading(true)
    try {
      const detail = await getChatSession(sessionId)
      setActiveSessionId(detail.id)
      setMessages(detail.messages)
      setShowSessionList(false)
    } catch (e) {
      console.error('加载会话详情失败', e)
    } finally {
      setLoading(false)
    }
  }

  // 清理打字机 interval
  useEffect(() => {
    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
      }
    }
  }, [])

  const startTyping = (messageId: string, fullText: string) => {
    // 先显示为空，逐步追加
    setDisplayedTexts((prev) => ({ ...prev, [messageId]: '' }))
    setTypingDone((prev) => {
      const next = new Set(prev)
      next.delete(messageId)
      return next
    })

    let index = 0
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current)
    }

    typingIntervalRef.current = setInterval(() => {
      index++
      if (index >= fullText.length) {
        if (typingIntervalRef.current) {
          clearInterval(typingIntervalRef.current)
          typingIntervalRef.current = null
        }
        setDisplayedTexts((prev) => ({ ...prev, [messageId]: fullText }))
        setTypingDone((prev) => new Set(prev).add(messageId))
      } else {
        setDisplayedTexts((prev) => ({ ...prev, [messageId]: fullText.slice(0, index) }))
      }
    }, 12)
  }

  const handleSend = async (content: string) => {
    if (!content.trim() || !activeSessionId || loading) return

    const userMsg: ChatMessage = {
      id: 'temp-' + Date.now(),
      session_id: activeSessionId,
      role: 'user',
      content: content.trim(),
      model_name: null,
      tokens_used: null,
      meta_json: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setMessages((prev: ChatMessage[]) => [...prev, userMsg])
    setInputValue('')
    setLoading(true)

    try {
      const assistantMsg = await sendChatMessage(activeSessionId, content.trim())
      setMessages((prev: ChatMessage[]) =>
        prev.filter((m: ChatMessage) => m.id !== userMsg.id).concat(assistantMsg)
      )
      // 启动打字机效果
      startTyping(assistantMsg.id, assistantMsg.content)
    } catch (e) {
      console.error('发送消息失败', e)
      const errorMsg: ChatMessage = {
        id: 'error-' + Date.now(),
        session_id: activeSessionId,
        role: 'assistant',
        content: '抱歉，发送消息时出错了，请稍后再试。',
        model_name: null,
        tokens_used: null,
        meta_json: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      setMessages((prev: ChatMessage[]) =>
        prev.filter((m: ChatMessage) => m.id !== userMsg.id).concat(errorMsg)
      )
      startTyping(errorMsg.id, errorMsg.content)
    } finally {
      setLoading(false)
    }
  }

  const handleNewSession = async () => {
    try {
      const session = await createChatSession(projectId)
      setSessions((prev: ChatSession[]) => [session, ...prev])
      setActiveSessionId(session.id)
      setMessages([])
      setShowSessionList(false)
    } catch (e) {
      console.error('创建会话失败', e)
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('确定要删除这个会话吗？')) return
    try {
      await deleteChatSession(sessionId)
      setSessions((prev: ChatSession[]) => prev.filter((s) => s.id !== sessionId))
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
        setMessages([])
      }
    } catch (e) {
      console.error('删除会话失败', e)
    }
  }

  if (!isOpen) return null

  return (
    <>
      {/* 遮罩层 */}
      <div
        className="fixed inset-0 z-40 bg-black/10 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* 抽屉 */}
      <div className="fixed right-0 top-0 bottom-0 z-50 w-[420px] max-w-full glass-panel border-l border-white/60 shadow-2xl flex flex-col">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center">
              <span className="text-sm">🤖</span>
            </div>
            <span className="text-sm font-medium text-slate-700">AI 创作助手</span>
          </div>
          <div className="flex items-center space-x-1">
            <button
              onClick={() => setShowSessionList(!showSessionList)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors"
              title="会话列表"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* 会话列表面板 */}
        {showSessionList && (
          <div className="border-b border-slate-100 bg-slate-50/50">
            <div className="px-4 py-2 flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">会话列表</span>
              <button
                onClick={handleNewSession}
                className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
              >
                + 新建会话
              </button>
            </div>
            <div className="max-h-40 overflow-y-auto">
              {sessions.map((s: ChatSession) => (
                <div
                  key={s.id}
                  className={`flex items-center justify-between px-4 py-2 text-xs transition-colors group ${
                    s.id === activeSessionId
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <button
                    onClick={() => loadSession(s.id)}
                    className="flex-1 text-left truncate"
                  >
                    {s.title || '未命名会话'}
                  </button>
                  <button
                    onClick={() => handleDeleteSession(s.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all"
                    title="删除会话"
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              ))}
              {sessions.length === 0 && (
                <div className="px-4 py-3 text-xs text-slate-400 text-center">暂无会话</div>
              )}
            </div>
          </div>
        )}

        {/* 消息区 */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {initLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="w-5 h-5 border-2 border-indigo-200 border-t-indigo-500 rounded-full animate-spin" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-50 flex items-center justify-center">
                <span className="text-2xl">🤖</span>
              </div>
              <p className="text-sm text-slate-500">我是你的 AI 创作助手</p>
              <p className="text-xs text-slate-400 text-center max-w-[280px]">
                可以问我关于剧情、角色、写作技巧的问题，我会结合你的项目上下文来回答
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-[320px]">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSend(prompt)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-slate-100 text-xs text-slate-600 hover:border-indigo-200 hover:text-indigo-600 transition-colors shadow-sm"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg: ChatMessage) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'user' ? (
                  <div className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed bg-indigo-500 text-white rounded-br-md">
                    {msg.content}
                  </div>
                ) : typingDone.has(msg.id) ? (
                  <div
                    className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed bg-white border border-slate-100 text-slate-700 rounded-bl-md shadow-sm chat-markdown"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                  />
                ) : (
                  <div className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed bg-white border border-slate-100 text-slate-700 rounded-bl-md shadow-sm whitespace-pre-wrap">
                    {displayedTexts[msg.id] || ''}
                    <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 align-text-bottom animate-pulse" />
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-slate-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div className="flex space-x-1">
                  <div className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="flex items-end space-x-2">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend(inputValue)
                }
              }}
              placeholder="输入问题，按 Enter 发送..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 transition-all"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={() => handleSend(inputValue)}
              disabled={!inputValue.trim() || loading}
              className="mb-0.5 p-2 rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

export default AIChatDrawer
