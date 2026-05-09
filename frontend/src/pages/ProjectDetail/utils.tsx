import { getTask } from '../../api/task'

export const pollTask = async (
  taskId: string,
  onSuccess: () => void,
  onError?: (msg: string) => void,
  onProgress?: (progress: number, status: string) => void,
) => {
  const interval = setInterval(async () => {
    try {
      const task = await getTask(taskId)
      onProgress?.(task.progress || 0, task.status)
      if (task.status === 'success') {
        clearInterval(interval)
        onSuccess()
      } else if (task.status === 'failed') {
        clearInterval(interval)
        onError?.(task.error_msg || '任务失败')
      }
    } catch {
      // ignore polling errors
    }
  }, 3000)
}

export const getTaskStepLabel = (type: string, progress: number): string => {
  const labels: Record<string, Record<number, string>> = {
    architecture: {
      10: '初始化任务...',
      30: '生成核心种子...',
      50: '生成角色动力学...',
      70: '保存角色状态...',
      90: '生成世界观与情节...',
    },
    directory: {
      10: '初始化任务...',
      40: 'LLM 生成章节目录...',
      70: '解析并保存目录...',
    },
    chapter: {
      10: '初始化任务...',
      30: '读取前置资产...',
      50: 'LLM 生成章节正文...',
      80: '保存章节草稿...',
    },
    drama_plan: {
      10: '初始化任务...',
      30: '分析章节分组...',
      60: '生成剧集计划...',
    },
    drama_episode: {
      10: '初始化任务...',
      50: 'LLM 生成单集脚本...',
    },
    batch_chapters: {
      5: '初始化批量任务...',
      10: '读取资产与章节列表...',
      50: '逐章生成正文中...',
      90: '保存最后章节...',
    },
    drama_batch: {
      5: '初始化批量任务...',
      10: '读取剧集与章节列表...',
      50: '逐集生成脚本中...',
      90: '保存最后剧集脚本...',
    },
  }
  const map = labels[type] || {}
  const keys = Object.keys(map).map(Number).sort((a, b) => b - a)
  for (const k of keys) {
    if (progress >= k) return map[k]
  }
  return '处理中...'
}

export const ProgressBar = ({ progress, label }: { progress: number; label?: string }) => (
  <div className="w-full space-y-1">
    <div className="flex justify-between text-xs text-gray-600">
      <span>{label || '生成中...'}</span>
      <span>{progress}%</span>
    </div>
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div
        className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
        style={{ width: `${Math.max(progress, 5)}%` }}
      ></div>
    </div>
  </div>
)

export const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    draft: 'bg-slate-100 text-slate-600',
    draft_generated: 'bg-indigo-100 text-indigo-700',
    generating: 'bg-amber-100 text-amber-700',
    finalized: 'bg-emerald-100 text-emerald-700',
  }
  const label: Record<string, string> = {
    draft: '草稿',
    draft_generated: '已生成',
    generating: '生成中',
    finalized: '已终稿',
  }
  return (
    <span className={`inline-block text-xs px-2 py-1 rounded-full ${map[status] || map.draft}`}>
      {label[status] || status}
    </span>
  )
}

export const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
