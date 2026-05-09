import React from 'react'

interface Dialogue {
  speaker: string
  content: string
  emotion?: string
  note?: string
}

interface Audio {
  bgm?: string
  sfx?: string[]
}

interface Shot {
  shot_num: number
  type?: string
  duration?: string
  visual?: string
  action?: string
  dialogue?: Dialogue
  camera_movement?: string
  audio?: Audio
}

interface Scene {
  scene_num: number
  source_chapter_range?: string
  mapped_beat_num?: number
  location?: string
  time?: string
  interior_exterior?: string
  characters?: string[]
  mood?: string
  shots: Shot[]
}

interface ScriptData {
  episode_num?: number
  title?: string
  total_duration?: string
  total_shots?: number
  scenes: Scene[]
  adaptation_notes?: string
}

interface ScriptViewerProps {
  script: ScriptData | Record<string, any> | null
  className?: string
}

const ScriptViewer: React.FC<ScriptViewerProps> = ({ script, className = '' }) => {
  if (!script || !script.scenes || !Array.isArray(script.scenes)) {
    return (
      <div className={`text-xs text-slate-400 italic ${className}`}>
        暂无脚本数据
      </div>
    )
  }

  const data = script as ScriptData

  return (
    <div className={`space-y-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">
            {data.title || `第${data.episode_num || '?'}集`}
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            总时长 {data.total_duration || '-'} · {data.total_shots || 0} 个镜头
          </p>
        </div>
      </div>

      {/* Scenes */}
      {data.scenes.map((scene) => (
        <div key={scene.scene_num} className="space-y-3">
          {/* Scene Header */}
          <div className="flex items-start space-x-2 bg-slate-50/60 rounded-lg px-3 py-2 border border-white/60">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider mt-0.5">
              场景 {scene.scene_num}
            </span>
            <div className="flex-1">
              <div className="flex items-center space-x-2 flex-wrap">
                {scene.location && (
                  <span className="text-xs font-medium text-slate-700">{scene.location}</span>
                )}
                {scene.interior_exterior && (
                  <span className="text-xs text-slate-400">({scene.interior_exterior})</span>
                )}
                {scene.time && (
                  <span className="text-xs text-slate-400">· {scene.time}</span>
                )}
                {scene.mood && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-100">
                    {scene.mood}
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2 mt-1 flex-wrap">
                {scene.characters && scene.characters.length > 0 && (
                  <span className="text-xs text-slate-400">
                    出场：{scene.characters.join('、')}
                  </span>
                )}
                {scene.source_chapter_range && (
                  <span className="text-xs text-slate-400">
                    来源：{scene.source_chapter_range}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Shots */}
          <div className="space-y-2 pl-2">
            {scene.shots.map((shot) => (
              <div
                key={shot.shot_num}
                className="border-l-2 border-emerald-200 pl-3 py-1"
              >
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-xs font-bold text-emerald-600">
                    镜头 {shot.shot_num}
                  </span>
                  {shot.type && (
                    <span className="text-xs text-slate-500">{shot.type}</span>
                  )}
                  {shot.duration && (
                    <span className="text-xs text-slate-400">{shot.duration}</span>
                  )}
                  {shot.camera_movement && (
                    <span className="text-xs text-slate-400">{shot.camera_movement}</span>
                  )}
                </div>

                {shot.visual && (
                  <p className="text-xs text-slate-600 leading-relaxed">
                    <span className="text-slate-400 mr-1">画面</span>
                    {shot.visual}
                  </p>
                )}
                {shot.action && (
                  <p className="text-xs text-slate-600 leading-relaxed mt-0.5">
                    <span className="text-slate-400 mr-1">动作</span>
                    {shot.action}
                  </p>
                )}

                {shot.dialogue && shot.dialogue.content && (
                  <div className="mt-1.5 bg-white/60 rounded-lg px-3 py-2 border border-white/60">
                    <div className="flex items-center space-x-2 mb-0.5">
                      <span className="text-xs font-semibold text-indigo-600">
                        {shot.dialogue.speaker}
                      </span>
                      {shot.dialogue.emotion && (
                        <span className="text-xs text-slate-400">
                          {shot.dialogue.emotion}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-800 leading-relaxed">
                      {shot.dialogue.content}
                    </p>
                    {shot.dialogue.note && (
                      <p className="text-xs text-slate-400 mt-0.5">
                        备注：{shot.dialogue.note}
                      </p>
                    )}
                  </div>
                )}

                {shot.audio && (shot.audio.bgm || (shot.audio.sfx && shot.audio.sfx.length > 0)) && (
                  <div className="flex items-center space-x-2 mt-1 flex-wrap">
                    {shot.audio.bgm && (
                      <span className="text-xs text-slate-400">
                        BGM: {shot.audio.bgm}
                      </span>
                    )}
                    {shot.audio.sfx && shot.audio.sfx.length > 0 && (
                      <span className="text-xs text-slate-400">
                        SFX: {shot.audio.sfx.join(', ')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Adaptation Notes */}
      {data.adaptation_notes && (
        <div className="border-t border-slate-200/60 pt-3 mt-2">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
            改编说明
          </h4>
          <p className="text-xs text-slate-500 leading-relaxed whitespace-pre-wrap">
            {data.adaptation_notes}
          </p>
        </div>
      )}
    </div>
  )
}

export default ScriptViewer
