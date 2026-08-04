import { useEffect, useRef, useState, useCallback } from 'react'
import { getTask } from '../api/task'

interface UsePollingTaskOptions {
  interval?: number
  onSuccess?: () => void
  onError?: (msg: string) => void
  onProgress?: (progress: number, status: string) => void
}

export function usePollingTask(taskId: string | null, options: UsePollingTaskOptions = {}) {
  const { interval = 3000, onSuccess, onError, onProgress } = options
  const [isPolling, setIsPolling] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  const startPolling = useCallback(
    (id: string) => {
      if (intervalRef.current) return
      setIsPolling(true)
      setProgress(0)
      setStatus('pending')
      setError(null)

      intervalRef.current = setInterval(async () => {
        try {
          const task = await getTask(id)
          setProgress(task.progress || 0)
          setStatus(task.status)
          onProgress?.(task.progress || 0, task.status)

          if (task.status === 'success') {
            stopPolling()
            onSuccess?.()
          } else if (task.status === 'failed') {
            stopPolling()
            const msg = task.error_msg || '任务失败'
            setError(msg)
            onError?.(msg)
          }
        } catch (err: any) {
          if (err.response?.status === 404) {
            stopPolling()
            setError('任务不存在或已被删除')
            onError?.('任务不存在或已被删除')
            return
          }
          // ignore other polling errors
        }
      }, interval)
    },
    [interval, onSuccess, onError, onProgress, stopPolling]
  )

  useEffect(() => {
    if (taskId) {
      startPolling(taskId)
    } else {
      stopPolling()
    }
    return () => stopPolling()
  }, [taskId, startPolling, stopPolling])

  return { isPolling, progress, status, error, startPolling, stopPolling }
}
