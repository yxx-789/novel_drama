# test_foreshadowing_ledger.py
# -*- coding: utf-8 -*-
"""V3 P3-B 伏笔台账：merge_foreshadowing_delta / build_foreshadowing_reminder 纯规则单测。"""

from app.generator.foreshadowing_ledger import (
    SUBPLOT_IDLE_THRESHOLD,
    build_foreshadowing_reminder,
    build_known_by_constraints,
    merge_foreshadowing_delta,
)

# 玄幻：foreshadowing_intervals.mid = [25, 40]；touch_every = [15, 20]
GENRE = "玄幻"
METHOD = {"touch_every": [10, 15]}


def _empty_ledger():
    return {"entries": [], "unmatched": []}


# ---------------- merge_foreshadowing_delta ----------------

def test_added_creates_open_entry_with_genre_recovery_range():
    memory = {"foreshadowing_added": [{"name": "神秘铜匣", "note": "祖传之物", "known_by": ["主角"]}]}
    out = merge_foreshadowing_delta(_empty_ledger(), memory, GENRE, 3)
    assert len(out["entries"]) == 1
    e = out["entries"][0]
    assert e["status"] == "open"
    assert e["added_chapter"] == 3
    assert e["last_touch_chapter"] == 3
    assert e["planned_recovery_range"] == [25, 40]   # 玄幻 mid 区间
    assert e["known_by"] == ["主角"]
    assert e["subplot"] is False
    assert e["id"] and len(e["id"]) == 16


def test_duplicate_added_merges_instead_of_new_entry():
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "铜匣", "note": "埋设说明"}]},
        GENRE, 3,
    )
    out = merge_foreshadowing_delta(
        ledger,
        {"foreshadowing_added": [{"name": "铜匣", "note": "补充细节", "known_by": ["女配"]}]},
        GENRE, 6,
    )
    assert len(out["entries"]) == 1
    e = out["entries"][0]
    assert e["status"] == "touched"          # 同名已存在 → 视为触碰
    assert e["last_touch_chapter"] == 6
    assert e["note"] == "埋设说明；补充细节"
    assert e["known_by"] == ["女配"]          # 合并


def test_touched_updates_status_and_last_touch():
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "玉佩", "note": "信物"}]},
        GENRE, 2,
    )
    out = merge_foreshadowing_delta(ledger, {"foreshadowing_touched": ["玉佩"]}, GENRE, 8)
    e = out["entries"][0]
    assert e["status"] == "touched"
    assert e["last_touch_chapter"] == 8


def test_recovered_sets_status():
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "信纸", "note": "线索"}]},
        GENRE, 4,
    )
    out = merge_foreshadowing_delta(ledger, {"foreshadowing_recovered": ["信纸"]}, GENRE, 20)
    assert out["entries"][0]["status"] == "recovered"
    assert out["entries"][0]["last_touch_chapter"] == 20


def test_subplot_advanced_marks_subplot():
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "商会线", "note": "支线"}]},
        GENRE, 5,
    )
    out = merge_foreshadowing_delta(ledger, {"subplot_advanced": ["商会线"]}, GENRE, 12)
    e = out["entries"][0]
    assert e["subplot"] is True
    assert e["status"] == "touched"
    assert e["last_touch_chapter"] == 12


def test_touched_after_recovered_does_not_reopen():
    """P1 回归：已回收伏笔被 touched 顺带提及 → 不重开（status 保持 recovered，仅刷新 last_touch）。"""
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "玉佩", "note": "信物"}]},
        GENRE, 2,
    )
    ledger = merge_foreshadowing_delta(ledger, {"foreshadowing_recovered": ["玉佩"]}, GENRE, 20)
    assert ledger["entries"][0]["status"] == "recovered"
    out = merge_foreshadowing_delta(ledger, {"foreshadowing_touched": ["玉佩"]}, GENRE, 25)
    e = out["entries"][0]
    assert e["status"] == "recovered"
    assert e["last_touch_chapter"] == 25


def test_unknown_genre_falls_back_to_default_mid():
    """未知题材回退 DEFAULT_METHODOLOGY 的 mid=[20,40]，不报错。"""
    out = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "线索", "note": ""}]},
        "不存在的题材", 3,
    )
    e = out["entries"][0]
    assert e["planned_recovery_range"] == [20, 40]


def test_known_by_merged_deduped_and_preserves_order():
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "秘密", "note": "", "known_by": ["主角", "反派"]}]},
        GENRE, 1,
    )
    out = merge_foreshadowing_delta(ledger, {"foreshadowing_touched": ["秘密"]}, GENRE, 3)
    # touched 不带 known_by → 保持原值
    assert out["entries"][0]["known_by"] == ["主角", "反派"]


def test_name_drift_goes_to_unmatched():
    memory = {
        "foreshadowing_touched": ["不存在的X"],
        "foreshadowing_recovered": ["不存在的Y"],
        "subplot_advanced": ["不存在的Z"],
    }
    out = merge_foreshadowing_delta(_empty_ledger(), memory, GENRE, 5)
    kinds = {(u["type"], u["name"]) for u in out["unmatched"]}
    assert kinds == {("touched", "不存在的X"), ("recovered", "不存在的Y"), ("subplot", "不存在的Z")}
    assert all(u["chapter"] == 5 for u in out["unmatched"])
    assert out["entries"] == []


def test_tolerant_of_bad_inputs():
    # ledger 非 dict / 缺失
    out = merge_foreshadowing_delta(None, {"foreshadowing_added": [{"name": "X"}]}, GENRE, 1)
    assert out["entries"] and out["unmatched"] == []
    out2 = merge_foreshadowing_delta({}, None, GENRE, 1)
    assert out2 == {"entries": [], "unmatched": []}
    # memory 字段非列表 → 跳过不崩
    ledger = _empty_ledger()
    out3 = merge_foreshadowing_delta(ledger, {"foreshadowing_added": "not-a-list"}, GENRE, 1)
    assert out3["entries"] == []
    # added 项非 dict / 空名 → 跳过
    out4 = merge_foreshadowing_delta(_empty_ledger(), {"foreshadowing_added": [42, {"name": "  "}]}, GENRE, 1)
    assert out4["entries"] == []


# ---------------- build_foreshadowing_reminder ----------------

def _ledger_with(entries):
    return {"entries": entries, "unmatched": []}


def test_reminder_overdue_and_recovery_window():
    ledger = _ledger_with([
        # A：逾期未碰 + 进入回收窗口
        {"name": "A", "status": "open", "last_touch_chapter": 3, "planned_recovery_range": [20, 30], "subplot": False},
        # B：进入回收窗口，不逾期
        {"name": "B", "status": "touched", "last_touch_chapter": 10, "planned_recovery_range": [22, 28], "subplot": False},
        # C：已回收 → 不提醒
        {"name": "C", "status": "recovered", "last_touch_chapter": 12, "planned_recovery_range": [20, 30], "subplot": False},
    ])
    text = build_foreshadowing_reminder(ledger, current_chapter=25, methodology=METHOD)
    assert "该碰一下的伏笔" in text
    assert "A（已22章未碰）" in text           # 25-3=22 > 15
    assert "进入回收窗口" in text
    assert "A" in text and "B" in text          # 都在回收窗口
    assert "C" not in text                      # 已回收不提醒


def test_reminder_idle_subplot():
    ledger = _ledger_with([
        {"name": "支线", "status": "touched", "last_touch_chapter": 5, "planned_recovery_range": [30, 50], "subplot": True},
    ])
    text = build_foreshadowing_reminder(ledger, current_chapter=5 + SUBPLOT_IDLE_THRESHOLD + 1, methodology=METHOD)
    assert "已闲置的副线提醒" in text
    assert "支线" in text
    assert "闲置" in text


def test_reminder_subplot_not_idle_when_recently_touched():
    ledger = _ledger_with([
        {"name": "支线", "status": "touched", "last_touch_chapter": 10, "planned_recovery_range": [30, 50], "subplot": True},
    ])
    text = build_foreshadowing_reminder(ledger, current_chapter=15, methodology=METHOD)  # 闲置 5 章
    assert "已闲置的副线提醒" not in text


def test_reminder_empty_when_no_hits():
    assert build_foreshadowing_reminder(_ledger_with([]), 5, METHOD) == ""
    assert build_foreshadowing_reminder(_ledger_with([
        {"name": "X", "status": "recovered", "last_touch_chapter": 1, "planned_recovery_range": [1, 2], "subplot": False},
    ]), 5, METHOD) == ""


def test_reminder_tolerant_of_bad_inputs():
    assert build_foreshadowing_reminder(None, 5, None) == ""
    assert build_foreshadowing_reminder({"entries": "bad"}, 5, {}) == ""
    assert build_foreshadowing_reminder({"entries": [42]}, 5, {}) == ""
    # current_chapter 非 int → 空串，不抛 TypeError
    assert build_foreshadowing_reminder(_ledger_with([
        {"name": "A", "status": "open", "last_touch_chapter": 3, "planned_recovery_range": [1, 2], "subplot": False},
    ]), "不是数字", METHOD) == ""


def test_reminder_recovery_window_includes_endpoints():
    """回收窗口边界 lo/hi 均命中。"""
    # last_touch 保持很近，避免逾期提醒污染"回收窗口"断言
    ledger = _ledger_with([
        {"name": "A", "status": "touched", "last_touch_chapter": 20, "planned_recovery_range": [20, 25], "subplot": False},
        {"name": "B", "status": "touched", "last_touch_chapter": 25, "planned_recovery_range": [26, 30], "subplot": False},
    ])
    assert "A" in build_foreshadowing_reminder(ledger, current_chapter=20, methodology=METHOD)
    assert "A" in build_foreshadowing_reminder(ledger, current_chapter=25, methodology=METHOD)
    assert "B" not in build_foreshadowing_reminder(ledger, current_chapter=25, methodology=METHOD)
    assert "B" in build_foreshadowing_reminder(ledger, current_chapter=26, methodology=METHOD)


def test_reminder_last_touch_missing_falls_back_to_added():
    """last_touch_chapter 缺失 → 回退 added_chapter。"""
    ledger = _ledger_with([
        {"name": "A", "status": "open", "added_chapter": 3, "planned_recovery_range": [30, 50], "subplot": False},
    ])
    text = build_foreshadowing_reminder(ledger, current_chapter=5, methodology=METHOD)
    assert text == ""  # 5-3=2 未逾期、不在窗口
    text2 = build_foreshadowing_reminder(ledger, current_chapter=30, methodology=METHOD)
    assert "A" in text2  # 30 在回收窗口


def test_known_by_deduped_when_overlapping():
    """存量已知者与新已知者重叠时去重保序。"""
    ledger = merge_foreshadowing_delta(
        _empty_ledger(),
        {"foreshadowing_added": [{"name": "秘密", "note": "", "known_by": ["主角", "反派"]}]},
        GENRE, 1,
    )
    out = merge_foreshadowing_delta(
        ledger,
        {"foreshadowing_added": [{"name": "秘密", "note": "", "known_by": ["反派", " 配角 "]}]},
        GENRE, 3,
    )
    assert out["entries"][0]["known_by"] == ["主角", "反派", "配角"]


def test_entry_id_stable_across_calls():
    """id 是 name+added_chapter 的纯函数，跨调用可复现。"""
    a = merge_foreshadowing_delta(_empty_ledger(), {"foreshadowing_added": [{"name": "匣"}]}, GENRE, 3)
    b = merge_foreshadowing_delta(_empty_ledger(), {"foreshadowing_added": [{"name": "匣"}]}, GENRE, 3)
    assert a["entries"][0]["id"] == b["entries"][0]["id"]


# ---------------- build_known_by_constraints（信息约束，防 OOC） ----------------

def _constraint_entry(name, added, last, known_by, status="open", recovery=None, subplot=False):
    return {
        "name": name, "status": status, "added_chapter": added, "last_touch_chapter": last,
        "planned_recovery_range": recovery if recovery is not None else [20, 40],
        "subplot": subplot, "known_by": list(known_by) if known_by else [],
    }


def test_known_by_constraints_basic():
    """基本渲染格式：无提醒命中时只带埋设章。"""
    ledger = _ledger_with([
        _constraint_entry("铜匣", added=3, last=3, known_by=["主角", "反派"]),
    ])
    text = build_known_by_constraints(ledger, current_chapter=4, methodology=METHOD)
    assert text.startswith("- 铜匣：已知晓者 [主角, 反派]（第3章埋设）")


def test_known_by_constraints_includes_reason_suffix():
    """逾期 + 回收窗口命中 → 在埋设信息后追加原因短语。"""
    ledger = _ledger_with([
        _constraint_entry("玉佩", added=3, last=3, known_by=["主角"], recovery=[20, 40]),
    ])
    text = build_known_by_constraints(ledger, current_chapter=25, methodology=METHOD)
    # 25-3=22 > 15 → 逾期；25 ∈ [20,40] → 回收窗口
    assert "已22章未碰" in text
    assert "进入回收窗口" in text
    assert "（第3章埋设，已22章未碰，进入回收窗口）" in text


def test_known_by_constraints_excludes_recovered_abandoned():
    ledger = _ledger_with([
        _constraint_entry("A", added=1, last=1, known_by=["主角"], status="recovered"),
        _constraint_entry("B", added=1, last=1, known_by=["主角"], status="abandoned"),
    ])
    assert build_known_by_constraints(ledger, current_chapter=5, methodology=METHOD) == ""


def test_known_by_constraints_excludes_empty_known_by():
    ledger = _ledger_with([
        _constraint_entry("A", added=1, last=1, known_by=[]),
        _constraint_entry("B", added=1, last=1, known_by=None),
    ])
    assert build_known_by_constraints(ledger, current_chapter=5, methodology=METHOD) == ""


def test_known_by_constraints_recent_top5():
    """超过 limit 条时只取最近触碰的前 5 条（无提醒命中的旧条目不出现）。"""
    entries = [
        _constraint_entry(f"伏笔{i}", added=i, last=i, known_by=["主角"], recovery=[100, 200])
        for i in range(1, 7)
    ]
    text = build_known_by_constraints(_ledger_with(entries), current_chapter=10, methodology=METHOD)
    assert "伏笔1" not in text      # last=1 最旧，超出前 5
    for i in range(2, 7):
        assert f"伏笔{i}" in text


def test_known_by_constraints_reminder_hit_beyond_limit_included():
    """进入回收窗口的旧条目不因超出最近前 5 被丢弃——紧要项必须纳入。"""
    entries = [_constraint_entry("旧伏笔", added=1, last=1, known_by=["主角"], recovery=[20, 40])]
    for i in range(5):
        last = 20 + i
        entries.append(_constraint_entry(f"新伏笔{last}", added=1, last=last, known_by=["主角"], recovery=[100, 200]))
    text = build_known_by_constraints(_ledger_with(entries), current_chapter=25, methodology=METHOD)
    assert "旧伏笔" in text
    assert "进入回收窗口" in text


def test_known_by_constraints_dedup_recent_and_hit():
    """同一条既在最近前 5 又提醒命中 → 只渲染一次。"""
    entries = [
        _constraint_entry("铜匣", added=3, last=24, known_by=["主角"], recovery=[20, 40]),
        _constraint_entry("其它", added=2, last=2, known_by=["反派"], recovery=[100, 200]),
    ]
    text = build_known_by_constraints(_ledger_with(entries), current_chapter=25, methodology=METHOD)
    assert text.count("铜匣") == 1


def test_known_by_constraints_tolerant():
    """ledger / current_chapter / limit 非预期结构 → 空串或回退，不抛异常。"""
    assert build_known_by_constraints(None, 5, None) == ""
    assert build_known_by_constraints({"entries": "bad"}, 5, {}) == ""
    assert build_known_by_constraints({"entries": [42]}, 5, {}) == ""
    assert build_known_by_constraints(
        _ledger_with([_constraint_entry("A", added=1, last=1, known_by=["主角"])]),
        "不是数字", METHOD) == ""
    # limit 非正常值 → 回退默认 5
    text = build_known_by_constraints(
        _ledger_with([_constraint_entry("A", added=1, last=1, known_by=["主角"])]),
        5, METHOD, limit=0)
    assert "A" in text
