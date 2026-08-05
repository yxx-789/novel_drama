# 创作灵感策展 实施计划（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 采集器对热点做 LLM 策展（取正文 → 过滤 + 生成灵感点 + 质量分），加权排序入库；后端按 rank_score 返回；前端卡片展示灵感点。

**Architecture:** 采集器在抓取后对每分类 Top N 候选调 `get_feed_detail` 取正文，用 DeepSeek 批量策展，计算加权 `rank_score` 入库；`get_hot_notes` 改按 `rank_score` 排序并返回新字段；前端卡片显示 💡灵感点。

**Tech Stack:** Python（requests + psycopg2）+ DeepSeek API + SQLAlchemy + Alembic + React/TypeScript。

## Global Constraints

- 文案中性，**不得出现「小红书/xiaohongshu」字样**
- 只策展每分类初选 Top N（`CURATE_TOP_PER_CATEGORY` 默认 8），正文**只用于策展不入库**
- 加权公式：`rank_score = likes + collects*1.2 + shares*1.5 + comments*2 + quality_score*300`
- 不破坏既有功能（项目内 Tab、用它创建项目、AI 助手、主页）
- 前端 `npm run build` 零错误
- 更新 `docs/CHANGELOG.md`

---

### Task 1: HotTopic 模型加 4 列 + Alembic 迁移

**Files:**
- Modify: `backend/app/models/inspiration.py`
- Create: `backend/alembic/versions/xxxx_add_inspiration_curation_columns.py`（autogenerate）

**Interfaces:**
- Produces: `HotTopic` 新增 `comment_count: int`、`inspiration_hint: str|None`、`quality_score: int`、`rank_score: float`

- [ ] **Step 1: 模型加字段**

```python
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
# 现有字段之后加：
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    inspiration_hint: Mapped[str | None] = mapped_column(Text)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
```

（在 `from sqlalchemy import ...` 中加 `Float`）

- [ ] **Step 2: 生成并应用迁移**

```bash
docker compose exec -T backend alembic revision --autogenerate -m "add inspiration curation columns"
docker compose exec -T backend alembic upgrade head
docker compose exec -T db psql -U postgres -d ai_novel_studio -c "\d hot_topics"
```

预期：hot_topics 含 comment_count/inspiration_hint/quality_score/rank_score 四列。

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/inspiration.py backend/alembic/versions/
git commit -m "feat: add inspiration curation columns to HotTopic"
```

---

### Task 2: 采集器——取正文 + LLM 策展 + rank_score

**Files:**
- Modify: `scripts/xhs_hot_collector.py`
- Modify: `scripts/test_collector.py`

**Interfaces:**
- Consumes: `normalize_feeds`（已有，需保留 xsec_token 供详情）、`McpClient`
- Produces:
  - `fetch_detail(client, feed_id, xsec_token) -> str`（正文，截断 2000 字）
  - `_llm_curate(notes: list[dict]) -> list[dict]`（每项补 `usable`/`inspiration_hint`/`quality_score`；无 Key 时全部 usable、hint 空、分 0）
  - `compute_rank_score(row) -> float`
  - `collect_once()` 流程改为：搜索→normalize（含 `_xsec_token`）→按互动分取 Top N→取正文→LLM 策展→算 rank→过滤 usable→upsert

- [ ] **Step 1: normalize_feeds 保留 xsec_token（内部字段，入库前移除）**

在 `normalize_feeds` 的 row 加 `"_xsec_token": note.get("xsecToken") or ""`（`_` 前缀标记内部字段）。

- [ ] **Step 2: 新增 fetch_detail**

```python
def fetch_detail(client: McpClient, feed_id: str, xsec_token: str) -> str:
    """调用 get_feed_detail 取正文（截断 2000 字）。失败返回空串。"""
    try:
        result = client.call_tool(
            "get_feed_detail",
            {"feed_id": feed_id, "xsec_token": xsec_token, "load_all_comments": False},
        )
        # 从结果里提取正文（兼容嵌套结构）
        def _find_text(v):
            if isinstance(v, dict):
                for k in ("desc", "content", "title"):
                    if isinstance(v.get(k), str) and v[k]:
                        return v[k]
                for child in v.values():
                    t = _find_text(child)
                    if t:
                        return t
            return ""
        return _find_text(result)[:2000]
    except Exception:
        return ""
```

- [ ] **Step 3: 新增 LLM 策展**

```python
def _llm_curate(notes: list[dict]) -> list[dict]:
    """批量策展：判断能否当创作种子 + 生成灵感点 + 质量分。无 LLM Key 时全部放行。"""
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        for n in notes:
            n.update({"usable": True, "inspiration_hint": "", "quality_score": 0})
        return notes
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    items = "\n\n".join(
        f"[{i}] 标题：{n.get('title', '')}\n正文：{n.get('body', '')[:500]}" for i, n in enumerate(notes)
    )
    prompt = (
        "以下是从内容平台收集的热点笔记。判断每一条能否作为小说或短剧的创作种子"
        "（有叙事潜力：人物冲突、戏剧性情境、情感张力、意外转折等）。\n"
        "只返回 JSON 数组，格式："
        '[{"i": 0, "usable": true, "inspiration_hint": "可改编成…", "quality_score": 3}]'
        "，quality_score 为 1-5 的创作价值。usable=false 的 inspiration_hint 给空串。\n\n" + items
    )
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.3, "max_tokens": 2048},
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # 提取 JSON 数组
        import re
        m = re.search(r"\[[\s\S]*\]", content)
        if not m:
            raise ValueError("LLM 未返回 JSON 数组")
        results = json.loads(m.group(0))
        by_i = {r.get("i"): r for r in results if isinstance(r, dict)}
        for idx, n in enumerate(notes):
            r = by_i.get(idx, {})
            n.update({
                "usable": bool(r.get("usable", True)),
                "inspiration_hint": str(r.get("inspiration_hint") or "")[:300],
                "quality_score": int(r.get("quality_score") or 0),
            })
    except Exception as e:
        print(f"LLM 策展失败（放行全部）: {e}")
        for n in notes:
            n.update({"usable": True, "inspiration_hint": "", "quality_score": 0})
    return notes
```

- [ ] **Step 4: 新增 compute_rank_score**

```python
def compute_rank_score(row: dict) -> float:
    return (
        float(row.get("likes") or 0) * 1.0
        + float(row.get("collects") or 0) * 1.2
        + float(row.get("shares") or 0) * 1.5
        + float(row.get("comment_count") or 0) * 2.0
        + float(row.get("quality_score") or 0) * 300
    )
```

- [ ] **Step 5: 改 collect_once 流水线**

```python
# 在 collect_once 内，每个分类：
cat_rows.sort(key=lambda r: (r["likes"] * 1.0 + r["collects"] * 1.2 + r["shares"] * 1.5), reverse=True)
cat_rows = cat_rows[:CURATE_TOP_PER_CATEGORY]

# 取正文
for row in cat_rows:
    row["body"] = fetch_detail(client, row["note_id"], row.get("_xsec_token", ""))
    row["comment_count"] = 0  # 搜索结果的 interactInfo 无评论数，详情里若有再取；默认 0

# LLM 策展
curated = _llm_curate(cat_rows)

# 过滤 + 算 rank + 清理内部字段
clean_rows = []
for row in curated:
    if not row["usable"]:
        continue
    row["rank_score"] = compute_rank_score(row)
    row.pop("body", None)
    row.pop("_xsec_token", None)
    clean_rows.append(row)
if clean_rows:
    total += upsert_hot_topics(clean_rows, batch_ts)
```

（`CURATE_TOP_PER_CATEGORY = int(os.getenv("CURATE_TOP_PER_CATEGORY", "8"))` 加到常量区）

- [ ] **Step 6: upsert SQL 加新列**

`upsert_hot_topics` 的 INSERT/UPDATE 加 `comment_count`、`inspiration_hint`、`quality_score`、`rank_score` 四列（`ON CONFLICT` 更新时一并更新）。

- [ ] **Step 7: 扩展测试** `scripts/test_collector.py`

```python
from xhs_hot_collector import compute_rank_score

def test_compute_rank_score():
    row = {"likes": 100, "collects": 10, "shares": 5, "comment_count": 3, "quality_score": 4}
    assert compute_rank_score(row) == pytest.approx(100 + 10*1.2 + 5*1.5 + 3*2 + 4*300)

def test_normalize_keeps_xsec_token():
    feeds = [{"id": "n1", "xsecToken": "tok", "noteCard": "{'displayTitle': '标题'}"}]
    rows = normalize_feeds(feeds, "甜宠")
    assert rows[0]["_xsec_token"] == "tok"
```

- [ ] **Step 8: 测试 + 提交**

```bash
cd scripts && python3 -m pytest test_collector.py -q   # 预期全过
```

```bash
git add scripts/
git commit -m "feat: curate inspirations with LLM and weighted ranking"
```

---

### Task 3: 后端按 rank_score 排序 + 返回新字段

**Files:**
- Modify: `backend/app/services/inspiration_service.py`

**Interfaces:**
- Consumes: `HotTopic`（含新 4 列，Task 1）
- Produces: `get_hot_notes` 按 `rank_score` DESC，返回含 `comment_count`/`inspiration_hint`/`quality_score`

- [ ] **Step 1: 改 get_hot_notes**

```python
stmt = select(HotTopic).order_by(HotTopic.rank_score.desc(), HotTopic.likes.desc()).limit(limit)
```
返回 dict 增加：
```python
"comment_count": n.comment_count,
"inspiration_hint": n.inspiration_hint,
"quality_score": n.quality_score,
```

- [ ] **Step 2: 验证**——后端容器 reload 后 `docker compose exec -T backend python -c "import app.services.inspiration_service; print('ok')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/inspiration_service.py
git commit -m "feat: rank inspirations by weighted score"
```

---

### Task 4: 前端卡片显示灵感点

**Files:**
- Modify: `frontend/src/api/inspiration.ts`
- Modify: `frontend/src/pages/ProjectDetail/InspirationTab.tsx`

**Interfaces:**
- Consumes: 后端 `get_hot_notes` 新返回字段（Task 3）

- [ ] **Step 1: HotNote 接口加字段**

```ts
export interface HotNote {
  // ... 现有字段
  comment_count?: number
  inspiration_hint?: string | null
  quality_score?: number
}
```

- [ ] **Step 2: 卡片显示灵感点**

在 `InspirationTab.tsx` 卡片内（标题之下、摘要之上）加：
```tsx
{note.inspiration_hint && (
  <p className="text-xs text-indigo-600 mt-1 leading-relaxed">
    💡 {note.inspiration_hint}
  </p>
)}
```

- [ ] **Step 3: 构建验证**——`cd frontend && npm run build` 零错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/inspiration.ts frontend/src/pages/ProjectDetail/InspirationTab.tsx
git commit -m "feat: show inspiration hint on cards"
```

---

### Task 5: 文档 + 全量验证

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: CHANGELOG**——`[未发布]` 加「灵感策展」小节：LLM 策展（取正文+过滤+灵感点+质量分）、加权排序、hot_topics 新列、前端灵感点展示。

- [ ] **Step 2: 全量构建**——`cd frontend && npm run build` 零错误；后端 `docker compose exec -T backend python -m pytest app/tests/ -q` 通过

- [ ] **Step 3: 实测采集器**——`cd scripts && python3 xhs_hot_collector.py`（可设 `CURATE_TOP_PER_CATEGORY=3` 快速验证），确认库里有 inspiration_hint/quality_score/rank_score 非空的行

- [ ] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record inspiration curation"
```

---

## 验收清单

- [ ] `hot_topics` 含 comment_count/inspiration_hint/quality_score/rank_score
- [ ] 采集器对候选取正文 + LLM 策展，usable=false 被过滤，usable=true 带灵感点/质量分
- [ ] `get_hot_notes` 按 rank_score 排序，返回新字段（无平台字样）
- [ ] 前端卡片显示 💡灵感点
- [ ] 既有功能回归正常；`npm run build` 零错误
