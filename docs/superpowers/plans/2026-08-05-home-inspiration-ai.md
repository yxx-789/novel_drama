# 主页创作灵感（完整版）+ 主页 AI 助手 实施计划（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V2 主页（项目列表页）展示完整版「创作灵感」（复用 InspirationTab，32 分类 + 搜索 + 完整列表），支持「用它创建项目」；主页加 AI 助手（复用 AIChatDrawer，无项目通用模式）。

**Architecture:** 前端复用现有组件：`InspirationTab` 加主页模式（无 projectId → 「用它创建项目」跳转创建页）；`ProjectCreate` 读 query 预填 + 创建后自动导入；`AIChatDrawer` 的 `projectId` 改可选（无项目 = 通用会话）。后端会话已支持 `project_id` 可选，预期免改。

**Tech Stack:** React + TypeScript + React Router + React Query。

## Global Constraints

- 文案中性，**不得出现「小红书」字样**
- 不破坏既有功能：项目内「创作灵感」Tab、项目内 AI 助手（带项目上下文）、创建项目流程、主页现状
- 前端 `npm run build`（tsc + vite）**零错误**
- 完成后更新 `docs/CHANGELOG.md`

---

### Task 1: InspirationTab 主页模式

**Files:**
- Modify: `frontend/src/pages/ProjectDetail/InspirationTab.tsx`

**Interfaces:**
- Consumes: `getInspirationCategories` / `getHotNotes` / `importInspiration`（`api/inspiration.ts`，已存在）
- Produces: `InspirationTab({ projectId?: string })`——无 `projectId` 时按钮为「用它创建项目」并跳转 `/projects/create?topic=&note_id=&summary=&likes=&author=&url=`

- [ ] **Step 1: 改写组件**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getInspirationCategories, getHotNotes, importInspiration, HotNote } from '../../api/inspiration'
import { queryClient } from '../../queryClient'
import { useToastStore } from '../../store/toast'

interface Props {
  projectId?: string
}

export default function InspirationTab({ projectId }: Props) {
  const navigate = useNavigate()
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
    mutationFn: (note: HotNote) => importInspiration(projectId!, note),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      addToast(`已导入灵感：${data.topic}`, 'success')
    },
    onError: (err: any) => addToast(err?.response?.data?.detail || '导入失败', 'error'),
  })

  const handlePrimaryAction = (note: HotNote) => {
    if (projectId) {
      if (window.confirm(`将「${note.title}」设为项目主题并作为创作参考？`)) {
        importMut.mutate(note)
      }
    } else {
      const params = new URLSearchParams({
        topic: note.title,
        note_id: note.note_id,
        summary: note.summary || '',
        likes: String(note.likes),
        author: note.author || '',
        url: note.url || '',
      })
      navigate(`/projects/create?${params.toString()}`)
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
              <button onClick={() => handlePrimaryAction(note)}
                className="shrink-0 ml-3 text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                {projectId ? '导入项目' : '用它创建项目'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 验证**——`cd frontend && npm run build` 零错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectDetail/InspirationTab.tsx
git commit -m "feat: add home mode to InspirationTab (create project from inspiration)"
```

---

### Task 2: ProjectCreate 预填 + 自动导入

**Files:**
- Modify: `frontend/src/pages/ProjectCreate.tsx`

**Interfaces:**
- Consumes: `createProject`（`api/project.ts`）、`importInspiration`（`api/inspiration.ts`）、`useSearchParams`
- Produces: 读取 `/projects/create?topic=&note_id=&summary=&likes=&author=&url=` 预填名称/主题；创建成功后若带 `note_id` 自动导入灵感（以表单中的主题为准）

- [ ] **Step 1: 改写组件**

```tsx
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { createProject } from '../api/project'
import { importInspiration } from '../api/inspiration'
import { queryClient } from '../queryClient'

function ProjectCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryTopic = searchParams.get('topic') || ''
  const inspiration = {
    note_id: searchParams.get('note_id') || '',
    title: queryTopic,
    summary: searchParams.get('summary') || '',
    likes: Number(searchParams.get('likes') || 0),
    url: searchParams.get('url') || '',
    author: searchParams.get('author') || '',
  }
  const [name, setName] = useState(queryTopic)
  const [topic, setTopic] = useState(queryTopic)
  const [genre, setGenre] = useState('')
  const [numChapters, setNumChapters] = useState(20)
  const [wordNumber, setWordNumber] = useState(3000)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      if (inspiration.note_id) {
        try {
          await importInspiration(data.id, { ...inspiration, title: topic || queryTopic })
        } catch (e) {
          console.error('导入灵感失败', e)
        }
      }
      navigate(`/projects/${data.id}`)
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建项目失败')
    },
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    mutation.mutate({
      name,
      topic: topic || undefined,
      genre: genre || undefined,
      num_chapters: numChapters,
      word_number: wordNumber,
    })
  }

  // ... 其余 JSX 不变（表单字段 name/topic/genre/numChapters/wordNumber 已预填）
  return (
    <div className="min-h-screen bg-gray-50">
      {/* 与现状一致，仅 name/topic 初始值来自 queryTopic */}
    </div>
  )
}

export default ProjectCreate
```

- [ ] **Step 2: 验证**——`cd frontend && npm run build` 零错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectCreate.tsx
git commit -m "feat: prefill project create from inspiration and auto-import"
```

---

### Task 3: ProjectList 集成（灵感区 + AI 助手按钮）

**Files:**
- Modify: `frontend/src/pages/ProjectList.tsx`

**Interfaces:**
- Consumes: `InspirationTab`（Task 1）、`AIChatDrawer`（Task 4）

- [ ] **Step 1: 集成**

在 `ProjectList.tsx`：
1. import 加：
```tsx
import InspirationTab from './ProjectDetail/InspirationTab'
import AIChatDrawer from '../components/AIChatDrawer'
```
2. 组件内加状态：`const [chatOpen, setChatOpen] = useState(false)`
3. Header 右侧按钮组（用户名/设置/退出 之前）加：
```tsx
<button onClick={() => setChatOpen(true)} className="btn-ghost">AI 助手</button>
```
4. `<main>` 最顶部（`{error && ...}` 之后、搜索栏之前）加：
```tsx
<div className="glass-panel p-5 space-y-3">
  <h2 className="text-sm font-serif font-medium text-slate-800">创作灵感</h2>
  <InspirationTab />
</div>
```
5. 组件底部（AISettingsDrawer 之后）加：
```tsx
<AIChatDrawer isOpen={chatOpen} onClose={() => setChatOpen(false)} />
```

- [ ] **Step 2: 验证**——`cd frontend && npm run build` 零错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectList.tsx
git commit -m "feat: add inspiration section and AI assistant to home page"
```

---

### Task 4: AIChatDrawer 通用模式 + api/chat

**Files:**
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/components/AIChatDrawer.tsx`

**Interfaces:**
- Consumes: 后端 `GET /api/chat-sessions`、`POST /api/chat-sessions`（`project_id` 可选，已支持）
- Produces: `listUserChatSessions()`；`AIChatDrawer({ projectId?: string, isOpen, onClose })`

- [ ] **Step 1: api/chat.ts 加通用会话列表函数**

```ts
export async function listUserChatSessions() {
  const res = await apiClient.get(`/api/chat-sessions`)
  return res.data as ChatSession[]
}
```

- [ ] **Step 2: AIChatDrawer 支持无 projectId**

1. Props 改：
```tsx
interface AIChatDrawerProps {
  projectId?: string
  isOpen: boolean
  onClose: () => void
}
```
2. 快捷问题改两组：
```tsx
const PROJECT_QUICK_PROMPTS = [
  '帮我完善这个角色设定',
  '这段剧情怎么改更有张力',
  '给这章写个更好的开头',
  '分析一下目前的剧情节奏',
]
const GENERAL_QUICK_PROMPTS = [
  '帮我构思一个小说开头',
  '推荐几个热门题材',
  '甜宠文怎么写出新意',
  '我的点子怎么变成完整故事',
]
```
3. 初始化 effect（`if (!isOpen || !projectId) return` 改为 `if (!isOpen) return`，列表按有无 projectId）：
```tsx
const list = projectId ? await listProjectChatSessions(projectId) : await listUserChatSessions()
...
const session = projectId ? await createChatSession(projectId) : await createChatSession()
```
4. `handleNewSession` 同样条件化：
```tsx
const session = projectId ? await createChatSession(projectId) : await createChatSession()
```
5. 空状态提示与快捷问题条件化：`{projectId ? PROJECT_QUICK_PROMPTS : GENERAL_QUICK_PROMPTS}`，文案提示在通用模式用「我是你的 AI 创作助手，可以帮你构思题材、点子、写作技巧」。

- [ ] **Step 3: 验证后端无项目会话**（V2 后端 :8000 已跑）

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"insp_test","password":"Test123456"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# 创建无项目会话
curl -s -X POST http://localhost:8000/api/chat-sessions -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}'
# 用返回的 id 发消息（应正常返回 AI 回复）
```
预期：创建成功（project_id=null），发消息返回 assistant 回复。

- [ ] **Step 4: 验证**——`cd frontend && npm run build` 零错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/chat.ts frontend/src/components/AIChatDrawer.tsx
git commit -m "feat: support general (no-project) mode in AI chat drawer"
```

---

### Task 5: 文档 + 全量验证

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: CHANGELOG**——`[未发布]` 新增「主页创作灵感 + 主页 AI 助手」小节，记录：主页灵感区（完整复用 InspirationTab + 用它创建项目 + 创建页预填/自动导入）、主页 AI 助手（AIChatDrawer 通用模式）。

- [ ] **Step 2: 前端构建**——`cd frontend && npm run build` 零错误

- [ ] **Step 3: 手动验证**
- 主页（localhost:5173）登录后：顶部「创作灵感」区显示完整分类 chips + 热点列表
- 点一条「用它创建项目」→ 创建页主题/名称已预填 → 创建 → 新项目自动带灵感（主题已设、生成时参考）
- 主页「AI 助手」按钮 → 抽屉打开，通用对话（无项目上下文）能收到 AI 回复
- 进一个项目 → 原「创作灵感」Tab 仍是「导入项目」行为；项目内 AI 助手仍带项目上下文

- [ ] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record home inspiration and AI assistant"
```

---

## 验收清单

- [ ] 主页顶部显示完整版创作灵感（分类/搜索/列表齐全，非缩水）
- [ ] 「用它创建项目」→ 预填 → 创建 → 自动导入灵感（主题/资产/生成参考）
- [ ] 主页 AI 助手通用对话正常
- [ ] 项目内 Tab 和项目内 AI 助手行为不变
- [ ] 无「小红书」字样；`npm run build` 零错误
