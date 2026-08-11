import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getAssetVersions, rollbackAsset } from '../api/asset'
import { useToastStore } from '../store/toast'

interface VersionHistoryProps {
  projectId: string
  assetType: string
  assetName: string
  currentVersion: number
}

const TRIGGER_LABEL: Record<string, string> = {
  generate: 'AI 生成',
  manual: '手动保存',
  rollback: '回滚',
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  return d.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function VersionHistory({
  projectId,
  assetType,
  assetName,
  currentVersion,
}: VersionHistoryProps) {
  const [open, setOpen] = useState(false)
  const [rolling, setRolling] = useState<number | null>(null)
  const queryClient = useQueryClient()
  const toast = useToastStore((s) => s.addToast)

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ['asset-versions', projectId, assetType],
    queryFn: () => getAssetVersions(projectId, assetType),
    enabled: open,
  })

  const handleRollback = async (version: number) => {
    if (!window.confirm(`确定回滚到 v${version} 吗？当前${assetName}将被替换（历史版本仍保留）。`)) return
    setRolling(version)
    try {
      await rollbackAsset(projectId, assetType, version)
      await queryClient.invalidateQueries({ queryKey: ['asset', projectId, assetType] })
      await queryClient.invalidateQueries({ queryKey: ['asset-versions', projectId, assetType] })
      toast(`已回滚到 v${version}`, 'success')
    } catch (err: any) {
      toast(err.response?.data?.detail || '回滚失败', 'warning')
    } finally {
      setRolling(null)
    }
  }

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
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        版本历史
        <span className="text-[10px] text-slate-400">v{currentVersion}</span>
      </button>

      {open && (
        <div className="mt-2 bg-white border border-slate-200 rounded-xl max-h-64 overflow-y-auto">
          {isLoading ? (
            <p className="text-xs text-slate-400 text-center py-4">加载中...</p>
          ) : versions.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-4">暂无历史版本</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {versions.map((v) => (
                <li key={v.id} className="px-3 py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium text-slate-700">v{v.version}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                        {TRIGGER_LABEL[v.trigger_type] || v.trigger_type}
                      </span>
                      {v.version === currentVersion && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600">当前</span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {formatTime(v.created_at)}
                      {v.guidance ? ` · ${v.guidance.slice(0, 30)}${v.guidance.length > 30 ? '…' : ''}` : ''}
                    </p>
                  </div>
                  {v.version !== currentVersion && (
                    <button
                      onClick={() => handleRollback(v.version)}
                      disabled={rolling !== null}
                      className="shrink-0 text-[10px] px-2 py-1 rounded-md border border-slate-200 text-slate-500 hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-600 transition-colors disabled:opacity-50"
                    >
                      {rolling === v.version ? '回滚中...' : '回滚到此版本'}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
