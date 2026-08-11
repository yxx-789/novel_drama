import { useState } from 'react'

interface GuidancePanelProps {
  assetName: string
  generating: boolean
  onGenerateWithGuidance: (guidance: string) => void
}

export default function GuidancePanel({ assetName, generating, onGenerateWithGuidance }: GuidancePanelProps) {
  const [open, setOpen] = useState(false)
  const [guidance, setGuidance] = useState('')

  return (
    <div className="shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors ${
          open
            ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
            : 'border-gray-300 text-gray-600 hover:bg-gray-50'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        优化提示词
        <svg className={`w-3 h-3 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="mt-2 p-3 bg-indigo-50/40 border border-indigo-100 rounded-xl">
          <textarea
            value={guidance}
            onChange={(e) => setGuidance(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 text-sm leading-relaxed rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100 resize-y"
            placeholder={`告诉模型想怎么优化当前${assetName}：侧重什么、调整什么、保留什么…`}
          />
          <div className="flex items-center justify-between mt-2">
            <span className="text-[10px] text-slate-400">将基于当前{assetName}全文 + 你的提示词重新生成</span>
            <button
              onClick={() => {
                onGenerateWithGuidance(guidance.trim())
              }}
              disabled={generating}
              className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0 text-xs py-1.5 px-4"
            >
              {generating ? '生成中...' : `带提示词生成${assetName}`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
