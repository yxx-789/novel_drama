import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getLLMConfig, updateLLMConfig, testLLMConfig } from '../api/user'
import { queryClient } from '../queryClient'
import { useToastStore } from '../store/toast'

interface AISettingsDrawerProps {
  isOpen: boolean
  onClose: () => void
}

export default function AISettingsDrawer({ isOpen, onClose }: AISettingsDrawerProps) {
  const { addToast } = useToastStore()
  const [showKey, setShowKey] = useState(false)

  const { data: config, isLoading } = useQuery({
    queryKey: ['llmConfig'],
    queryFn: getLLMConfig,
    enabled: isOpen,
  })

  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')

  // Sync form when config loads
  useEffect(() => {
    if (config) {
      setApiKey(config.api_key || '')
      setBaseUrl(config.base_url || '')
      setModel(config.model || '')
    }
  }, [config])

  const updateMutation = useMutation({
    mutationFn: updateLLMConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmConfig'] })
      addToast('配置已保存', 'success')
    },
    onError: (err: any) => {
      addToast(err?.response?.data?.detail || '保存失败', 'error')
    },
  })

  const testMutation = useMutation({
    mutationFn: testLLMConfig,
    onSuccess: (data) => {
      if (data.success) {
        addToast(data.message, 'success')
      } else {
        addToast(data.message, 'error')
      }
    },
    onError: (err: any) => {
      addToast(err?.response?.data?.detail || '测试失败', 'error')
    },
  })

  const handleSave = () => {
    const payload: { api_key?: string | null; base_url?: string | null; model?: string | null } = {}
    if (apiKey !== config?.api_key) payload.api_key = apiKey || null
    if (baseUrl !== config?.base_url) payload.base_url = baseUrl || null
    if (model !== config?.model) payload.model = model || null
    updateMutation.mutate(payload)
  }

  const handleTest = () => {
    testMutation.mutate({
      api_key: apiKey || null,
      base_url: baseUrl || null,
      model: model || null,
    })
  }

  const handleReset = () => {
    setApiKey('')
    setBaseUrl('')
    setModel('')
    updateMutation.mutate({ api_key: null, base_url: null, model: null })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="relative w-full max-w-md bg-white shadow-2xl h-full overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Header */}
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-serif font-medium text-slate-800">AI 模型配置</h2>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Status */}
          {isLoading ? (
            <p className="text-sm text-slate-400">加载中...</p>
          ) : (
            <div className={`text-xs px-3 py-2 rounded-lg ${
              config?.source === 'user_custom'
                ? 'bg-indigo-50 text-indigo-600'
                : 'bg-slate-50 text-slate-500'
            }`}>
              {config?.source === 'user_custom'
                ? '当前使用自定义 API Key'
                : '当前使用平台默认 Key（免费体验）'}
            </div>
          )}

          {/* Form */}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1.5">API Key</label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={config?.source === 'platform_default' ? '使用平台默认 Key' : '请输入您的 API Key'}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg py-2.5 pl-3 pr-10 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showKey ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1.5">Base URL（可选）</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={config?.base_url || 'https://api.deepseek.com'}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg py-2.5 px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1.5">Model（可选）</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={config?.model || 'deepseek-chat'}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg py-2.5 px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300"
              />
            </div>
          </div>

          {/* Hint */}
          <p className="text-xs text-slate-400 leading-relaxed">
            配置自己的 API Key 可获得更高额度和更快响应。
            留空则使用平台默认 Key。
          </p>

          {/* Actions */}
          <div className="space-y-2">
            <div className="flex space-x-2">
              <button
                onClick={handleTest}
                disabled={testMutation.isPending}
                className="flex-1 py-2.5 px-4 bg-white border border-slate-200 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                {testMutation.isPending ? '测试中...' : '测试连接'}
              </button>
              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="flex-1 py-2.5 px-4 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
              >
                {updateMutation.isPending ? '保存中...' : '保存配置'}
              </button>
            </div>
            {config?.source === 'user_custom' && (
              <button
                onClick={handleReset}
                disabled={updateMutation.isPending}
                className="w-full py-2.5 px-4 text-rose-500 text-sm font-medium rounded-lg hover:bg-rose-50 transition-colors disabled:opacity-50"
              >
                恢复平台默认
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
