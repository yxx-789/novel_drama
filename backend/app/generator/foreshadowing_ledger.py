# foreshadowing_ledger.py
# -*- coding: utf-8 -*-
"""
伏笔台账（V3 P3-B）：纯规则，无 LLM 调用。

把散落在每章 `chapter_memory_extract_prompt` 输出的伏笔信息收敛成一本台账，
追踪 触碰 / 回收 / 逾期 / 副线闲置，供写前注入提醒。

台账结构（ProjectAsset.content_json）：
{
  "entries": [
    {
      "id": "hash(name+added_chapter)",
      "name": "伏笔名",
      "note": "埋设说明",
      "added_chapter": 3,
      "last_touch_chapter": 3,
      "planned_recovery_range": [30, 50],   // 由题材参数表 foreshadowing_intervals.mid 给区间
      "status": "open | touched | recovered | abandoned",
      "subplot": false,                     // 是否为副线（>1 章持续推进的支线）
      "known_by": ["主角"],                 // 事实级 known_by：谁知道这条伏笔/信息
      "tags": []
    }
  ],
  "unmatched": [                            // LLM 命名漂移的挂起项，不静默丢弃
    {"chapter": 4, "type": "touched", "name": "……"}
  ]
}

关键接口：
- merge_foreshadowing_delta(ledger, memory, genre, chapter_num) -> dict   合并单章记忆（纯规则）
- build_foreshadowing_reminder(ledger, current_chapter, methodology) -> str  写前提醒（纯规则）
"""

import hashlib

from app.generator.genre_methodology import DEFAULT_METHODOLOGY, get_genre_methodology

# 副线闲置阈值（章）：last_touch 距今超过 N 章即提醒
SUBPLOT_IDLE_THRESHOLD = 20


def _entry_id(name: str, chapter_num: int) -> str:
    """稳定 id：hash(name + added_chapter)，跨调用可复现。"""
    raw = f"{name}|{chapter_num}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _norm_names(items) -> list[str]:
    """规范化列表字段：只保留非空字符串，去首尾空白。"""
    if not isinstance(items, list):
        return []
    out = []
    for x in items:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _find_entry_index(entries: list, name: str) -> int | None:
    """按伏笔名精确匹配（归一化后）；未命中返回 None。"""
    target = name.strip()
    for i, e in enumerate(entries):
        if isinstance(e, dict) and str(e.get("name", "")).strip() == target:
            return i
    return None


def _merge_known(base: list | None, extra: list) -> list:
    """合并 known_by：去重保序，保留原顺序在前；存量与新输入都规范化（去空/去首尾空白）。"""
    seen = set()
    merged = []
    for x in _norm_names(base) + _norm_names(extra):
        if x not in seen:
            seen.add(x)
            merged.append(x)
    return merged


def _new_entry(name: str, note: str, chapter_num: int, known_by: list, recovery_range: list) -> dict:
    return {
        "id": _entry_id(name, chapter_num),
        "name": name,
        "note": note,
        "added_chapter": chapter_num,
        "last_touch_chapter": chapter_num,
        "planned_recovery_range": list(recovery_range),
        "status": "open",
        "subplot": False,
        "known_by": list(known_by),
        "tags": [],
    }


def _default_ledger() -> dict:
    return {"entries": [], "unmatched": []}


def merge_foreshadowing_delta(ledger: dict, memory: dict, genre: str, chapter_num: int) -> dict:
    """
    把单章结构化记忆（extract_chapter_memory 输出）合并进台账。

    - `foreshadowing_added`（[{name, note, known_by}]）→ 新增 entry（status=open，
      planned_recovery_range 按题材参数表 foreshadowing_intervals.mid 取；
      同名已存在则视为触碰，合并 known_by / 更新 last_touch）。
    - `foreshadowing_touched`（[name]）→ 匹配设 status=touched + 更新 last_touch。
    - `foreshadowing_recovered`（[name]）→ 匹配设 status=recovered。
    - `subplot_advanced`（[name]）→ 匹配设 subplot=true + 更新 last_touch。
    - 匹配失败（LLM 命名漂移）→ 记入 unmatched，不静默丢弃。

    纯规则，无 LLM。ledger / memory 非预期结构时安全容错。
    """
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), list):
        ledger = _default_ledger()
    entries = ledger["entries"]
    unmatched = ledger["unmatched"] if isinstance(ledger.get("unmatched"), list) else ledger.setdefault("unmatched", [])

    methodology = get_genre_methodology(genre)
    intervals = methodology.get("foreshadowing_intervals") or {}
    # fallback 与 DEFAULT_METHODOLOGY 的 mid 对齐，避免区间默认值不一致误导
    default_mid = (DEFAULT_METHODOLOGY.get("foreshadowing_intervals") or {}).get("mid", [20, 40])
    mid = intervals.get("mid", default_mid)
    if not isinstance(mid, (list, tuple)) or len(mid) != 2:
        mid = default_mid
    recovery_range = [int(mid[0]), int(mid[1])]

    if not isinstance(memory, dict):
        return ledger

    # 1) 新埋设
    added = memory.get("foreshadowing_added")
    if isinstance(added, list):
        for item in added:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            note = str(item.get("note", "")).strip()
            known_by = _norm_names(item.get("known_by"))
            idx = _find_entry_index(entries, name)
            if idx is not None:
                # 同名已存在 → 视为触碰，合并（补充 note、刷新 last_touch、合并 known_by）
                e = entries[idx]
                if note:
                    e["note"] = note if not e.get("note") else f"{e['note']}；{note}"
                e["last_touch_chapter"] = chapter_num
                if e.get("status") not in ("recovered", "abandoned"):
                    e["status"] = "touched"
                e["known_by"] = _merge_known(e.get("known_by"), known_by)
            else:
                entries.append(_new_entry(name, note, chapter_num, known_by, recovery_range))

    # 2) 触碰既有伏笔
    # 守卫与 added 重复分支一致：已回收/已废弃的伏笔不因"顺带提及"被重开
    touched = memory.get("foreshadowing_touched")
    if isinstance(touched, list):
        for name in _norm_names(touched):
            idx = _find_entry_index(entries, name)
            if idx is None:
                unmatched.append({"chapter": chapter_num, "type": "touched", "name": name})
            else:
                entries[idx]["last_touch_chapter"] = chapter_num
                if entries[idx].get("status") not in ("recovered", "abandoned"):
                    entries[idx]["status"] = "touched"

    # 3) 回收既有伏笔
    recovered = memory.get("foreshadowing_recovered")
    if isinstance(recovered, list):
        for name in _norm_names(recovered):
            idx = _find_entry_index(entries, name)
            if idx is None:
                unmatched.append({"chapter": chapter_num, "type": "recovered", "name": name})
            else:
                entries[idx]["status"] = "recovered"
                entries[idx]["last_touch_chapter"] = chapter_num

    # 4) 副线推进
    subplots = memory.get("subplot_advanced")
    if isinstance(subplots, list):
        for name in _norm_names(subplots):
            idx = _find_entry_index(entries, name)
            if idx is None:
                unmatched.append({"chapter": chapter_num, "type": "subplot", "name": name})
            else:
                entries[idx]["subplot"] = True
                entries[idx]["last_touch_chapter"] = chapter_num
                if entries[idx].get("status") not in ("recovered", "abandoned"):
                    entries[idx]["status"] = "touched"

    return ledger


def _reminder_flags(e: dict, current_chapter: int, touch_max: int) -> list[tuple[str, str]]:
    """单条伏笔的提醒判定器（与 build_foreshadowing_reminder / build_known_by_constraints 共享）。

    返回 [(kind, suffix)]；kind ∈ overdue | recoverable | idle；无命中返回 []。
    - overdue：open/touched 且 `current_chapter - last_touch > touch_max` →「该碰一下」
    - recoverable：open/touched 且 `current_chapter ∈ planned_recovery_range` →「该准备回收」
    - idle：subplot=true 且闲置 > SUBPLOT_IDLE_THRESHOLD 章 →「副线闲置」

    已 recovered/abandoned 一律不参与；结构异常安全返回 []。
    """
    if not isinstance(e, dict):
        return []
    if e.get("status") in ("recovered", "abandoned"):
        return []
    last = e.get("last_touch_chapter")
    if not isinstance(last, int):
        last = e.get("added_chapter")
    if not isinstance(last, int):
        return []
    gap = current_chapter - last

    flags = []
    status = e.get("status", "open")
    if status in ("open", "touched"):
        if gap > touch_max:
            flags.append(("overdue", f"已{gap}章未碰"))
        rng = e.get("planned_recovery_range")
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            try:
                lo, hi = int(rng[0]), int(rng[1])
            except (TypeError, ValueError):
                lo, hi = 0, 0
            if lo <= current_chapter <= hi:
                flags.append(("recoverable", "进入回收窗口"))
    if e.get("subplot") and gap > SUBPLOT_IDLE_THRESHOLD:
        flags.append(("idle", f"已闲置{gap}章"))
    return flags


def build_foreshadowing_reminder(ledger: dict, current_chapter: int, methodology: dict) -> str:
    """
    写前生成伏笔/副线提醒文本；无命中返回空串。

    - 逾期未碰：open/touched 且 `current_chapter - last_touch_chapter > touch_every[1]` →「该碰一下」
    - 进入回收窗口：open/touched 且 `current_chapter ∈ planned_recovery_range` →「该考虑回收」
    - 副线闲置：subplot=true 且闲置 > SUBPLOT_IDLE_THRESHOLD 章 →「已闲置 N 章」

    纯规则，无 LLM。ledger / methodology 非预期结构时安全返回空串。
    """
    if not isinstance(ledger, dict):
        return ""
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        return ""
    if not isinstance(current_chapter, int):
        return ""
    methodology = methodology if isinstance(methodology, dict) else {}
    touch = methodology.get("touch_every", [12, 18])
    if not isinstance(touch, (list, tuple)) or len(touch) != 2:
        touch = [12, 18]
    touch_max = int(touch[1])

    overdue = []        # 逾期未碰
    recoverable = []    # 进入回收窗口未回收
    idle_subplots = []  # 副线闲置

    for e in entries:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name", "")).strip()
        if not name:
            continue
        flags = _reminder_flags(e, current_chapter, touch_max)
        for kind, suffix in flags:
            if kind == "overdue":
                overdue.append(f"{name}（{suffix}）")
            elif kind == "recoverable":
                recoverable.append(name)
            elif kind == "idle":
                idle_subplots.append(f"{name}（{suffix}）")

    parts = []
    if overdue:
        parts.append("该碰一下的伏笔：" + "；".join(overdue))
    if recoverable:
        parts.append("进入回收窗口、应准备回收的伏笔：" + "；".join(recoverable))
    if idle_subplots:
        parts.append("已闲置的副线提醒：" + "；".join(idle_subplots))
    return "；".join(parts)


def build_known_by_constraints(
    ledger: dict,
    current_chapter: int,
    methodology: dict | None = None,
    limit: int = 5,
) -> str:
    """
    写前生成 known_by 信息约束文本（防 OOC：除已知晓者外，其他角色不得提前知情/谈论）。

    从 open/touched 且 known_by 非空的伏笔中，取「最近触碰前 limit 条」∪「提醒命中
    （逾期/回收窗口/闲置）条目」并集去重，渲染成逐条约束。无命中返回空串。

    渲染格式（不含【信息约束】标题，由调用方包裹）：
        以下伏笔/秘密仅部分角色知晓，其他角色不得提前知情或谈论：
        - {name}：已知晓者 [{A, B}]（第{added}章埋设，已{N}章未碰）

    纯规则，无 LLM。ledger / methodology / limit 非预期结构时安全容错。
    """
    if not isinstance(ledger, dict):
        return ""
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        return ""
    if not isinstance(current_chapter, int):
        return ""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5
    if limit < 1:
        limit = 5

    methodology = methodology if isinstance(methodology, dict) else {}
    touch = methodology.get("touch_every", [12, 18])
    if not isinstance(touch, (list, tuple)) or len(touch) != 2:
        touch = [12, 18]
    touch_max = int(touch[1])

    # 候选：open/touched、known_by 非空、name 非空
    qual = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if e.get("status", "open") not in ("open", "touched"):
            continue
        name = str(e.get("name", "")).strip()
        if not name:
            continue
        known = _norm_names(e.get("known_by"))
        if not known:
            continue
        last = e.get("last_touch_chapter")
        if not isinstance(last, int):
            last = e.get("added_chapter")
        if not isinstance(last, int):
            last = 0
        added = e.get("added_chapter")
        if not isinstance(added, int):
            added = 0
        qual.append({
            "name": name,
            "known": known,
            "last": last,
            "added": added,
            "flags": _reminder_flags(e, current_chapter, touch_max),
        })

    if not qual:
        return ""

    # 提醒命中池：逾期/回收窗口/闲置的紧要项，即使不在最近前 limit 内也纳入
    hit = {q["name"]: q for q in qual if q["flags"]}
    # 最近触碰池：按 (last, added, name) 降序取前 limit 条
    recent_sorted = sorted(qual, key=lambda q: (q["last"], q["added"], q["name"]), reverse=True)
    combined = {q["name"]: q for q in recent_sorted[:limit]}
    combined.update(hit)  # hit 优先覆盖同名项

    # 排序：提醒命中在前，其余按最近触碰倒序（确定性、可解释）
    ordered = sorted(combined.values(), key=lambda q: (not bool(q["flags"]), -q["last"]))

    lines = []
    for q in ordered:
        reason = "，".join(s for _, s in q["flags"])
        suffix = f"，{reason}" if reason else ""
        lines.append(
            f"- {q['name']}：已知晓者 [{', '.join(q['known'])}]（第{q['added']}章埋设{suffix}）"
        )
    return "\n".join(lines)
