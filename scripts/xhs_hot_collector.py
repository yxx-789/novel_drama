"""小红书热点采集器：每天把热点写入 hot_topics 表。独立运行，不参与 Web 服务。"""
import ast
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import psycopg2
import requests
from psycopg2.extras import execute_batch

# 让 preset_categories 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.preset_categories import PRESET_CATEGORIES  # noqa: E402
from mcp_client import McpClient  # noqa: E402

XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060/mcp")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_novel_studio")
TOP_N_PER_CATEGORY = int(os.getenv("TOP_N_PER_CATEGORY", "20"))
CURATE_TOP_PER_CATEGORY = int(os.getenv("CURATE_TOP_PER_CATEGORY", "8"))


def _find_list(value: Any, key: str) -> list[dict]:
    if isinstance(value, dict):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        for child in value.values():
            found = _find_list(child, key)
            if found:
                return found
    return []


def _parse_note_card(note_card: Any) -> dict:
    """xiaohongshu-mcp 的 search 结果把 noteCard 作为 Python dict 字面量字符串返回，解析成 dict。"""
    if isinstance(note_card, dict):
        return note_card
    if isinstance(note_card, str):
        try:
            parsed = ast.literal_eval(note_card)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            return {}
    return {}


def normalize_feeds(feeds: list[dict], category: str) -> list[dict]:
    """把 MCP search 返回的 feeds 规范成入库行。

    真实结构（xiaohongshu-mcp search_feeds）：
      { "id": "68c0032c...", "xsecToken": "...", "noteCard": "{'type':'normal','displayTitle':...,'user':{...},'interactInfo':{...}}" }
    note_id 在顶层 `id`；标题/点赞/作者都嵌在 `noteCard`（字符串）。点赞数为字符串。
    """
    rows = []
    for f in feeds:
        note = f if isinstance(f, dict) else {}
        note_id = str(note.get("id") or note.get("noteId") or note.get("feedId") or "")
        if not note_id:
            continue
        card = _parse_note_card(note.get("noteCard"))
        title = card.get("displayTitle") or card.get("title") or note.get("title") or ""
        if not title:
            continue
        interact = card.get("interactInfo") or {}
        user = card.get("user") or {}
        row = {
            "category": category,
            "note_id": note_id[:64],
            "_xsec_token": note.get("xsecToken") or "",
            "title": str(title)[:255],
            "summary": (card.get("desc") or card.get("summary") or "")[:2000],
            "likes": int(interact.get("likedCount") or 0),
            "collects": int(interact.get("collectedCount") or 0),
            "shares": int(interact.get("sharedCount") or interact.get("shareCount") or 0),
            "url": f"https://www.xiaohongshu.com/explore/{note_id}",
            "author": (user.get("nickname") or user.get("nickName") or "")[:128],
            "source": "xiaohongshu",
        }
        rows.append(row)
    return rows


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


def compute_rank_score(row: dict) -> float:
    return (
        float(row.get("likes") or 0) * 1.0
        + float(row.get("collects") or 0) * 1.2
        + float(row.get("shares") or 0) * 1.5
        + float(row.get("comment_count") or 0) * 2.0
        + float(row.get("quality_score") or 0) * 300
    )


def upsert_hot_topics(rows: list[dict], fetched_at: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO hot_topics
                    (id, category, note_id, title, summary, likes, collects, shares, url, author, source,
                     comment_count, inspiration_hint, quality_score, rank_score, fetched_at)
                VALUES (gen_random_uuid(), %(category)s, %(note_id)s, %(title)s, %(summary)s,
                        %(likes)s, %(collects)s, %(shares)s, %(url)s, %(author)s, %(source)s,
                        %(comment_count)s, %(inspiration_hint)s, %(quality_score)s, %(rank_score)s, %(fetched_at)s)
                ON CONFLICT (note_id) DO UPDATE SET
                    likes = EXCLUDED.likes,
                    collects = EXCLUDED.collects,
                    shares = EXCLUDED.shares,
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    comment_count = EXCLUDED.comment_count,
                    inspiration_hint = EXCLUDED.inspiration_hint,
                    quality_score = EXCLUDED.quality_score,
                    rank_score = EXCLUDED.rank_score,
                    fetched_at = EXCLUDED.fetched_at
            """
            for row in rows:
                row["fetched_at"] = fetched_at
            execute_batch(cur, sql, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def collect_once() -> dict:
    client = McpClient(XHS_MCP_URL)
    total = 0
    errors = []
    # 单一批次共用一个时间戳：get_hot_notes 用 fetched_at == max(fetched_at) 圈"最近一批"，
    # 必须保证同一批所有行 fetched_at 完全一致，否则过滤后只剩少数行。
    batch_ts = datetime.now(timezone.utc).isoformat()
    try:
        client.connect()
        for cat in PRESET_CATEGORIES:
            cat_rows: list[dict] = []
            for kw in cat["keywords"]:
                try:
                    result = client.call_tool("search_feeds", {"keyword": kw})
                    feeds = _find_list(result, "feeds")
                    cat_rows.extend(normalize_feeds(feeds, cat["name"]))
                except Exception as e:
                    errors.append(f"{cat['name']}/{kw}: {e}")
            # 按互动分排序取 Top N，再取每个分类前 K 条做策展
            cat_rows.sort(key=lambda r: (r["likes"] * 1.0 + r["collects"] * 1.2 + r["shares"] * 1.5), reverse=True)
            cat_rows = cat_rows[:TOP_N_PER_CATEGORY]
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
    finally:
        client.close()
    return {"total_upserted": total, "errors": errors}


if __name__ == "__main__":
    report = collect_once()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        print("部分分类失败（可能未登录或限流）:", report["errors"])
