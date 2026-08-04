import { QueryClient } from '@tanstack/react-query'
import { useToastStore } from './store/toast'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 分钟内数据视为新鲜
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      onError: (err: any) => {
        const msg = err?.response?.data?.detail || '操作失败，请重试'
        useToastStore.getState().addToast(msg, 'error')
      },
    },
  },
})
