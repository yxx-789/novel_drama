"""小红书热点采集器：每天把热点写入 hot_topics 表。独立运行，不参与 Web 服务。"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import execute_batch

# 让 preset_categories 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.preset_categories import PRESET_CATEGORIES  # noqa: E402
from mcp_client import McpClient  # noqa: E402

XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060/mcp")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_novel_studio")
TOP_N_PER_CATEGORY = int(os.getenv("TOP_N_PER_CATEGORY", "20"))


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


def normalize_feeds(feeds: list[dict], category: str) -> list[dict]:
    """把 MCP search 返回的 feeds 规范成入库行。"""
    rows = []
    for f in feeds:
        note = f if isinstance(f, dict) else {}
        title = note.get("title") or note.get("displayTitle") or ""
        if not title:
            continue
        row = {
            "category": category,
            "note_id": str(note.get("noteId") or note.get("feedId") or ""),
            "title": str(title)[:255],
            "summary": (note.get("desc") or note.get("summary") or "")[:2000],
            "likes": int((note.get("interactInfo") or {}).get("likedCount") or 0),
            "collects": int((note.get("interactInfo") or {}).get("collectedCount") or 0),
            "shares": int((note.get("interactInfo") or {}).get("shareCount") or 0),
            "url": note.get("url") or "",
            "author": (note.get("user") or {}).get("nickname") or "",
            "source": "xiaohongshu",
        }
        rows.append(row)
    return rows


def upsert_hot_topics(rows: list[dict], fetched_at: str) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO hot_topics
                    (id, category, note_id, title, summary, likes, collects, shares, url, author, source, fetched_at)
                VALUES (gen_random_uuid(), %(category)s, %(note_id)s, %(title)s, %(summary)s,
                        %(likes)s, %(collects)s, %(shares)s, %(url)s, %(author)s, %(source)s, %(fetched_at)s)
                ON CONFLICT (note_id) DO UPDATE SET
                    likes = EXCLUDED.likes,
                    collects = EXCLUDED.collects,
                    shares = EXCLUDED.shares,
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
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
    client.connect()
    total = 0
    errors = []
    # 单一批次共用一个时间戳：get_hot_notes 用 fetched_at == max(fetched_at) 圈"最近一批"，
    # 必须保证同一批所有行 fetched_at 完全一致，否则过滤后只剩少数行。
    batch_ts = datetime.now(timezone.utc).isoformat()
    try:
        for cat in PRESET_CATEGORIES:
            cat_rows: list[dict] = []
            for kw in cat["keywords"]:
                try:
                    result = client.call_tool("search_feeds", {"keyword": kw})
                    feeds = _find_list(result, "feeds")
                    cat_rows.extend(normalize_feeds(feeds, cat["name"]))
                except Exception as e:
                    errors.append(f"{cat['name']}/{kw}: {e}")
            # 按点赞排序取 Top N
            cat_rows.sort(key=lambda r: r["likes"], reverse=True)
            cat_rows = cat_rows[:TOP_N_PER_CATEGORY]
            if cat_rows:
                total += upsert_hot_topics(cat_rows, batch_ts)
    finally:
        client.close()
    return {"total_upserted": total, "errors": errors}


if __name__ == "__main__":
    report = collect_once()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        print("部分分类失败（可能未登录或限流）:", report["errors"])
