import { useToastStore } from '../store/toast'

const typeStyles: Record<string, string> = {
  success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  info: 'bg-slate-50 border-slate-200 text-slate-800',
}

const typeIcon: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
}

function Toast() {
  const { toasts, removeToast } = useToastStore()
  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col items-center gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg border shadow-sm text-sm font-medium min-w-[200px] max-w-[400px] animate-[fadeIn_0.2s_ease-out] ${typeStyles[t.type]}`}
        >
          <span className="text-xs">{typeIcon[t.type]}</span>
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            className="text-xs opacity-50 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

export default Toast
