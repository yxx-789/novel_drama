import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getInspirationCategories, getHotNotes, importInspiration, HotNote } from '../../api/inspiration'
import { queryClient } from '../../queryClient'
import { useToastStore } from '../../store/toast'

interface Props {
  projectId: string
}

export default function InspirationTab({ projectId }: Props) {
  const { addToast } = useToastStore()
  const [category, setCategory] = useState('')
  const [keyword, setKeyword] = useState('')

  const { data: categories = [] } = useQuery({
    queryKey: ['inspirationCategories'],
    queryFn: getInspirationCategories,
  })

  const { data: notes = [], refetch } = useQuery({
    queryKey: ['inspirationHot', category, keyword],
    queryFn: () => getHotNotes(category, keyword),
  })

  const importMut = useMutation({
    mutationFn: (note: HotNote) => importInspiration(projectId, note),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      addToast(`已导入灵感：${data.topic}`, 'success')
    },
    onError: (err: any) => addToast(err?.response?.data?.detail || '导入失败', 'error'),
  })

  const handleImport = (note: HotNote) => {
    if (window.confirm(`将「${note.title}」设为项目主题并作为创作参考？`)) {
      importMut.mutate(note)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => { setCategory(''); setKeyword(''); refetch() }}
          className="text-xs px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-600 hover:bg-slate-50">
          全部
        </button>
        {categories.map((c) => (
          <button key={c} onClick={() => setCategory(c)}
            className={`text-xs px-3 py-1.5 rounded-full border ${
              category === c ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}>
            {c}
          </button>
        ))}
        <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索标题/摘要…"
          className="ml-auto w-48 bg-slate-50 border border-slate-200 rounded-lg py-1.5 px-3 text-sm" />
        <button onClick={() => refetch()}
          className="text-xs px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50">
          刷新
        </button>
      </div>

      {notes.length === 0 ? (
        <p className="text-sm text-slate-400 italic">暂无热点数据，请先运行采集器更新。</p>
      ) : (
        <div className="space-y-2">
          {notes.map((note) => (
            <div key={note.note_id} className="flex items-start justify-between bg-white rounded-lg border border-slate-200/70 px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{note.title}</p>
                {note.summary && <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{note.summary}</p>}
                <p className="text-xs text-slate-400 mt-1">👍 {note.likes} · {note.author || '未知作者'}</p>
              </div>
              <button onClick={() => handleImport(note)}
                className="shrink-0 ml-3 text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                导入项目
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
