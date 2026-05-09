import React, { useState } from 'react'
import type { DramaEpisode } from '../api/drama'
import ScriptViewer from './ScriptViewer'

interface ChapterInfo {
  id: string
  chapter_num: number
  title: string | null
}

interface EpisodeCardProps {
  episode: DramaEpisode
  chapters: ChapterInfo[]
  prevEpisode?: DramaEpisode | null
  isGenerating?: boolean
  isSelected?: boolean
  onToggleSelect?: () => void
  onGenerateScript?: () => void
  onExport?: (format: 'json' | 'md' | 'csv') => void
  onUpdateTitle?: (title: string) => void
  onUpdateSourceChapters?: (sourceChapters: string) => void
  onUpdateOutline?: (outline: Record<string, any>) => void
  className?: string
}

const statusConfig: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  pending: { label: '待计划', color: 'text-slate-500', bg: 'bg-slate-50', dot: 'bg-slate-300' },
  planned: { label: '已计划', color: 'text-amber-600', bg: 'bg-amber-50', dot: 'bg-amber-400' },
  outlined: { label: '已大纲', color: 'text-blue-600', bg: 'bg-blue-50', dot: 'bg-blue-400' },
  script_ready: { label: '脚本就绪', color: 'text-emerald-600', bg: 'bg-emerald-50', dot: 'bg-emerald-400' },
}

const EpisodeCard: React.FC<EpisodeCardProps> = ({
  episode,
  chapters,
  prevEpisode,
  isGenerating = false,
  isSelected = false,
  onToggleSelect,
  onGenerateScript,
  onExport,
  onUpdateTitle,
  onUpdateSourceChapters,
  onUpdateOutline,
  className = '',
}) => {
  const [expanded, setExpanded] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState(episode.title || '')
  const [showAddChapters, setShowAddChapters] = useState(false)
  const [editingOutline, setEditingOutline] = useState(false)

  const status = statusConfig[episode.status] || statusConfig.pending
  const sourceChapterNums = episode.source_chapters
    ? episode.source_chapters.split(',').map((s) => parseInt(s.trim())).filter((n) => !isNaN(n))
    : []

  const assignedChapterNums = new Set(sourceChapterNums)
  const availableChapters = chapters.filter((c) => !assignedChapterNums.has(c.chapter_num))

  const handleTitleSave = () => {
    if (onUpdateTitle && titleDraft !== episode.title) {
      onUpdateTitle(titleDraft)
    }
    setEditingTitle(false)
  }

  const handleRemoveChapter = (chapterNum: number) => {
    if (!onUpdateSourceChapters) return
    const next = sourceChapterNums.filter((n) => n !== chapterNum).join(',')
    onUpdateSourceChapters(next)
  }

  const handleAddChapter = (chapterNum: number) => {
    if (!onUpdateSourceChapters) return
    const next = [...sourceChapterNums, chapterNum].sort((a, b) => a - b).join(',')
    onUpdateSourceChapters(next)
    setShowAddChapters(false)
  }

  const outline = episode.outline_json
  const script = episode.script_json

  return (
    <div className={`glass-panel p-4 card-hover ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3 flex-1">
          {onToggleSelect && (
            <input
              type="checkbox"
              checked={isSelected}
              onChange={onToggleSelect}
              className="mt-1.5 rounded border-slate-300 text-slate-600 focus:ring-slate-200"
            />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2 flex-wrap">
              <span className="text-sm font-medium text-slate-500">第{episode.episode_num}集</span>
              {editingTitle ? (
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={titleDraft}
                    onChange={(e) => setTitleDraft(e.target.value)}
                    onBlur={handleTitleSave}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleTitleSave()
                      if (e.key === 'Escape') {
                        setTitleDraft(episode.title || '')
                        setEditingTitle(false)
                      }
                    }}
                    autoFocus
                    className="text-sm font-semibold text-slate-900 bg-white/80 border border-slate-200 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-slate-300"
                  />
                </div>
              ) : (
                <h3
                  className="text-sm font-semibold text-slate-900 cursor-pointer hover:text-slate-600 transition-colors"
                  onClick={() => onUpdateTitle && setEditingTitle(true)}
                  title={onUpdateTitle ? '点击编辑标题' : ''}
                >
                  {episode.title || '未命名'}
                </h3>
              )}
              <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium ${status.color} ${status.bg}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
                <span>{status.label}</span>
              </span>
            </div>

            {/* Source Chapters */}
            <div className="mt-2 flex items-center flex-wrap gap-1.5">
              <span className="text-xs text-slate-400 mr-1">来源章节</span>
              {sourceChapterNums.map((num) => {
                const ch = chapters.find((c) => c.chapter_num === num)
                return (
                  <span
                    key={num}
                    className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-600 text-xs border border-indigo-100"
                  >
                    <span>第{num}章{ch ? ` ${ch.title}` : ''}</span>
                    {onUpdateSourceChapters && (
                      <button
                        onClick={() => handleRemoveChapter(num)}
                        className="text-indigo-400 hover:text-indigo-700 ml-0.5"
                        title="移除"
                      >
                        ×
                      </button>
                    )}
                  </span>
                )
              })}
              {onUpdateSourceChapters && availableChapters.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowAddChapters((v) => !v)}
                    className="text-xs px-2 py-0.5 rounded-md border border-dashed border-slate-300 text-slate-400 hover:text-slate-600 hover:border-slate-400 transition-colors"
                  >
                    + 添加
                  </button>
                  {showAddChapters && (
                    <div className="absolute top-full left-0 mt-1 z-10 glass-panel p-2 w-48 max-h-48 overflow-y-auto shadow-lg border border-white/60">
                      {availableChapters.sort((a, b) => a.chapter_num - b.chapter_num).map((ch) => (
                        <button
                          key={ch.id}
                          onClick={() => handleAddChapter(ch.chapter_num)}
                          className="w-full text-left text-xs text-slate-600 px-2 py-1.5 rounded hover:bg-white/60 transition-colors"
                        >
                          第{ch.chapter_num}章 {ch.title}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
          {onGenerateScript && (
            <button
              onClick={onGenerateScript}
              disabled={isGenerating}
              className="text-xs font-bold text-emerald-600 hover:text-emerald-700 disabled:opacity-50 transition-colors uppercase"
            >
              {isGenerating ? '生成中...' : script ? '重新生成' : '生成脚本'}
            </button>
          )}
          {(outline || script) && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs font-bold text-slate-400 hover:text-slate-700 transition-colors uppercase"
            >
              {expanded ? '收起' : '展开'}
            </button>
          )}
          {script && onExport && (
            <div className="flex items-center space-x-1">
              <span className="text-xs text-slate-300 uppercase">导出</span>
              {(['md', 'json', 'csv'] as const).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => onExport(fmt)}
                  className="text-xs font-bold text-slate-400 hover:text-slate-600 transition-colors uppercase"
                  title={`导出 ${fmt.toUpperCase()}`}
                >
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Context Navigation */}
      {prevEpisode && prevEpisode.script_json && (
        <div className="mt-3 p-2.5 rounded-lg bg-slate-50/40 border border-white/40">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-bold text-slate-400 uppercase ">前集续接</span>
            <span className="text-xs text-slate-400">
              第{prevEpisode.episode_num}集《{prevEpisode.title || '未命名'}》
            </span>
          </div>
          <p className="text-xs text-slate-500 line-clamp-2">
            {extractCliffhanger(prevEpisode.script_json)}
          </p>
        </div>
      )}

      {/* Expanded Content */}
      {expanded && (
        <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
          {/* Outline */}
          {outline && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-bold text-slate-500 uppercase ">分集大纲</h4>
                {onUpdateOutline && (
                  <button
                    onClick={() => setEditingOutline((v) => !v)}
                    className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    {editingOutline ? '完成' : '编辑'}
                  </button>
                )}
              </div>
              {editingOutline && onUpdateOutline ? (
                <OutlineEditor outline={outline} onSave={onUpdateOutline} onCancel={() => setEditingOutline(false)} />
              ) : (
                <OutlineViewer outline={outline} />
              )}
            </div>
          )}

          {/* Script */}
          {script && (
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">分镜剧本</h4>
              <ScriptViewer script={script} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function extractCliffhanger(scriptJson: Record<string, any>): string {
  const scenes = scriptJson.scenes || []
  if (scenes.length === 0) return '（无前集脚本信息）'
  const lastScene = scenes[scenes.length - 1]
  const shots = lastScene.shots || []
  if (shots.length === 0) return '（无前集脚本信息）'
  const lastShot = shots[shots.length - 1]
  const dialogue = lastShot.dialogue || {}
  if (dialogue.content) {
    return `最后台词 — ${dialogue.speaker || '?'}：${dialogue.content}`
  }
  return lastShot.visual || '（无前集结尾信息）'
}

function OutlineViewer({ outline }: { outline: Record<string, any> }) {
  return (
    <div className="space-y-3 bg-slate-50/40 rounded-xl p-4 border border-white/60">
      {outline.duration_estimate && (
        <p className="text-xs text-slate-400">预估时长：{outline.duration_estimate}</p>
      )}

      {outline.hook?.first_3s && (
        <div>
          <span className="text-xs font-bold text-amber-600 uppercase ">开局钩子（3秒）</span>
          <div className="mt-1 space-y-0.5">
            {outline.hook.first_3s.visual && (
              <p className="text-xs text-slate-600"><span className="text-slate-400">画面</span> {outline.hook.first_3s.visual}</p>
            )}
            {outline.hook.first_3s.action && (
              <p className="text-xs text-slate-600"><span className="text-slate-400">动作</span> {outline.hook.first_3s.action}</p>
            )}
            {outline.hook.first_3s.dialogue && (
              <p className="text-xs text-slate-600"><span className="text-slate-400">台词</span> {outline.hook.first_3s.dialogue}</p>
            )}
          </div>
        </div>
      )}

      {outline.story_beats && Array.isArray(outline.story_beats) && outline.story_beats.length > 0 && (
        <div>
          <span className="text-xs font-bold text-slate-500 uppercase ">故事节拍</span>
          <div className="mt-1 space-y-2">
            {outline.story_beats.map((beat: any) => (
              <div key={beat.beat_num} className="border-l-2 border-slate-200 pl-3 py-0.5">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-slate-500">节拍 {beat.beat_num}</span>
                  {beat.type && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">{beat.type}</span>
                  )}
                  {beat.duration && (
                    <span className="text-xs text-slate-400">{beat.duration}</span>
                  )}
                </div>
                {beat.description && (
                  <p className="text-xs text-slate-600 mt-0.5">{beat.description}</p>
                )}
                {beat.key_info && (
                  <p className="text-xs text-slate-400 mt-0.5">关键信息：{beat.key_info}</p>
                )}
                {beat.emotion && (
                  <p className="text-xs text-slate-400">情绪：{beat.emotion}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {outline.cliffhanger?.last_5s && (
        <div>
          <span className="text-xs font-bold text-rose-500 uppercase ">结尾悬念（5秒）</span>
          <div className="mt-1 space-y-0.5">
            {outline.cliffhanger.last_5s.visual && (
              <p className="text-xs text-slate-600"><span className="text-slate-400">画面</span> {outline.cliffhanger.last_5s.visual}</p>
            )}
            {outline.cliffhanger.last_5s.action && (
              <p className="text-xs text-slate-600"><span className="text-slate-400">动作</span> {outline.cliffhanger.last_5s.action}</p>
            )}
            {outline.cliffhanger.last_5s.dialogue && (
              <p className="text-xs text-slate-600"><span className="text-slate-400">台词</span> {outline.cliffhanger.last_5s.dialogue}</p>
            )}
            {outline.cliffhanger.last_5s.suspense_type && (
              <p className="text-xs text-rose-400 mt-0.5">悬念类型：{outline.cliffhanger.last_5s.suspense_type}</p>
            )}
          </div>
        </div>
      )}

      {outline.key_items && Array.isArray(outline.key_items) && outline.key_items.length > 0 && (
        <div className="flex items-center flex-wrap gap-1.5">
          <span className="text-xs text-slate-400">关键道具/信息</span>
          {outline.key_items.map((item: string, idx: number) => (
            <span key={idx} className="text-xs px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-100">{item}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function OutlineEditor({ outline, onSave, onCancel }: { outline: Record<string, any>; onSave: (o: Record<string, any>) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState(() => JSON.stringify(outline, null, 2))

  const handleSave = () => {
    try {
      const parsed = JSON.parse(draft)
      onSave(parsed)
    } catch (e) {
      alert('JSON 格式错误，请检查')
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={12}
        className="w-full text-xs font-mono bg-white/80 border border-slate-200 rounded-xl p-3 focus:outline-none focus:ring-1 focus:ring-slate-300"
      />
      <div className="flex items-center space-x-2">
        <button onClick={handleSave} className="btn-primary text-xs py-1.5 px-3">保存</button>
        <button onClick={onCancel} className="btn-secondary text-xs py-1.5 px-3">取消</button>
      </div>
    </div>
  )
}

export default EpisodeCard
